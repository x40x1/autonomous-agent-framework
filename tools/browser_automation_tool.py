import logging
import time
import json
import importlib
import subprocess
import sys
from typing import Optional, Dict, List, Union, Any

import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

class BrowserAutomationTool(BaseTool):
    name = "browser_automation"
    description = (
        "Controls a headless web browser (Chromium). USE WITH EXTREME CAUTION. "
        "Input is a dictionary specifying 'action' and associated parameters. "
        "Available actions: 'goto', 'fill', 'click', 'get_content', 'screenshot', 'close_browser'. "
        "Requires Playwright (`pip install playwright` and `playwright install`)."
        "'goto': {'url': '...'}"
        "'fill': {'selector': 'css_selector', 'value': 'text_to_fill'}"
        "'click': {'selector': 'css_selector'}"
        "'get_content': {'selector': 'css_selector (optional, defaults to body)'} -> Returns HTML content"
        "'screenshot': {'path': 'save_path.png'}"
        "'close_browser': {} -> Closes the current browser instance."
    )

    def __init__(self, timeout: int = 30000):  # Default timeout 30 seconds
        self.timeout = timeout
        self.browser = None
        self.page = None
        self.playwright = None
        self.is_playwright_available = self._check_playwright_installation()
        self.last_error = ""  # Added to store error details
        logger.info(f"BrowserAutomationTool initialized (Timeout: {self.timeout}ms). Playwright available: {self.is_playwright_available}")

    def _check_playwright_installation(self):
        """Check if playwright is installed and install browsers if needed"""
        try:
            # Check if playwright is installed
            importlib.import_module('playwright')
            
            # Try to verify browser installation
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info("Playwright is properly installed.")
                    return True
                else:
                    logger.error(f"Playwright not correctly installed: {result.stderr}")
                    return False
            except Exception as e:
                logger.error(f"Error checking playwright installation: {e}")
                return False
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright")
            return False

    def _ensure_browser_page(self):
        """Starts browser and page if not already running."""
        if not self.is_playwright_available:
            logger.error("Playwright is not properly installed. Cannot start browser.")
            self.last_error = "Playwright is not installed properly."
            return False
            
        # Now safely import playwright since we know it's available
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
        except ImportError:
            logger.error("Failed to import playwright even though it was detected earlier")
            self.last_error = "Playwright import failed."
            return False
            
        if self.page and self.browser and self.playwright:
            try:
                # Check if browser is still connected
                if self.browser.is_connected() and not self.page.is_closed():
                    return True  # Already running and connected
            except Exception:
                # If any error occurs, we'll close and restart
                pass

        # Close any existing instances
        self._close_browser()

        try:
            # Start a new playwright instance
            self.playwright = sync_playwright().start()
            # Launch browser with visible window (headless=False)
            self.browser = self.playwright.chromium.launch(headless=False)
            # Create a new page
            self.page = self.browser.new_page()
            self.page.set_default_timeout(self.timeout)
            logger.info("Started new browser instance and page")
            return True
        except Exception as e:
            logger.error(f"Failed to start browser: {e}", exc_info=True)
            self.last_error = str(e)
            self._close_browser()  # Clean up any partial resources
            return False

    def _close_browser(self):
        """Close and clean up browser resources properly"""
        try:
            if self.browser:
                self.browser.close()
                logger.info("Browser closed")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

        try:
            if self.playwright:
                self.playwright.stop()
                logger.info("Playwright stopped")
        except Exception as e:
            logger.warning(f"Error stopping playwright: {e}")

        # Reset all instances
        self.browser = None
        self.page = None
        self.playwright = None

    def execute(self, action_input=None, **kwargs):
        """Execute browser actions"""
        if not self.is_playwright_available:
            return "Error: Playwright is not installed or configured correctly. Please run 'pip install playwright' and 'playwright install'."
            
        # Handle string input (JSON) from agent
        if isinstance(action_input, str):
            try:
                action_input = json.loads(action_input)
                logger.info(f"Parsed JSON from action_input: {action_input}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from action_input: {e}")
                return f"Error: Failed to parse JSON input. Please provide a valid JSON dictionary. Error: {e}"

        # Use the parsed input or fall back to kwargs
        params = action_input if isinstance(action_input, dict) else kwargs

        action = params.get('action')
        if not action:
            return "Error: No action specified for browser_automation tool."

        action = str(action).lower()
        logger.info(f"Executing browser action: {action} with params: {params}")

        try:
            if action == 'close_browser':
                self._close_browser()
                return "Browser instance closed."

            # For all other actions, ensure browser is running
            if not self._ensure_browser_page():
                return f"Error: Failed to initialize browser. Details: {self.last_error}"

            # Import needed for PlaywrightTimeoutError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            
            if action == 'goto':
                url = params.get('url')
                if not url:
                    return "Error: 'url' parameter missing for 'goto' action."
                self.page.goto(url)
                return f"Successfully navigated to {url}. Current URL: {self.page.url}"

            elif action == 'fill':
                selector = params.get('selector')
                value = params.get('value')
                if not selector:
                    return "Error: 'selector' parameter missing for 'fill' action."
                if value is None:
                    return "Error: 'value' parameter missing for 'fill' action."
                self.page.locator(selector).fill(value)
                return f"Successfully filled selector '{selector}'."

            elif action == 'click':
                selector = params.get('selector')
                if not selector:
                    return "Error: 'selector' parameter missing for 'click' action."
                self.page.locator(selector).click()
                # Wait briefly for potential navigation or dynamic content changes
                time.sleep(1)
                return f"Successfully clicked selector '{selector}'. Current URL: {self.page.url}"

            elif action == 'get_content':
                # Get full page HTML content
                full_html = self.page.content()
                # Query all interactive elements like input, button, textarea, and select
                elements = self.page.query_selector_all("input, button, textarea, select")
                interactive = "\n".join([el.evaluate("node => node.outerHTML") for el in elements])
                # Limit content length if necessary
                max_len = 8000
                if len(full_html) > max_len:
                    full_html = full_html[:max_len] + "... (HTML content truncated)"
                if len(interactive) > max_len:
                    interactive = interactive[:max_len] + "... (interactive elements truncated)"
                return f"Full page HTML:\n{full_html}\n\nInteractive elements:\n{interactive}"

            elif action == 'screenshot':
                path = params.get('path')
                if not path:
                    return "Error: 'path' parameter missing for 'screenshot' action."
                self.page.screenshot(path=path)
                return f"Screenshot saved to '{path}'."

            else:
                return f"Error: Unknown browser_automation action '{action}'."

        except PlaywrightTimeoutError as e:
            logger.error(f"Playwright timeout error: {e}", exc_info=True)
            return f"Error: Timeout occurred during browser action '{action}': {e}"
        except Exception as e:
            logger.error(f"Browser automation error: {e}", exc_info=True)
            return f"Error during browser action '{action}': {e}"

    def __del__(self):
        """Destructor to ensure resources are properly cleaned up"""
        self._close_browser()