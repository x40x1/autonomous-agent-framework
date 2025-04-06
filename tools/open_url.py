import requests
from bs4 import BeautifulSoup
import logging
import re

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 8000  # Limit the amount of text scraped from a page

class OpenURLTool(BaseTool):
    name = "open_url"
    description = (
        "Opens and retrieves content from a specific URL. "
        "Input is the URL you want to access. "
        "Returns the text content of the webpage or an error message if the URL cannot be accessed."
    )

    def __init__(self):
        """Initialize the OpenURLTool."""
        logger.info("OpenURLTool initialized")

    def execute(self, url: str) -> str:
        """
        Opens a URL and returns its text content.
        
        Args:
            url: The URL to access.
            
        Returns:
            The text content of the webpage or an error message.
        """
        if not url:
            return "Error: No URL provided."
            
        # Basic URL validation
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url
            logger.info(f"URL modified to include schema: {url}")
            
        logger.info(f"Opening URL: {url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()  # Raise exception for bad status codes
            
            # Check content type to avoid parsing images, PDFs, etc.
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type and 'text/plain' not in content_type:
                logger.warning(f"Skipping non-HTML/text content type '{content_type}' for URL: {url}")
                return f"Error: Content type '{content_type}' is not scrapable text/html."
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()
                
            # Get text content, trying common main content tags first
            main_content = soup.find('main') or soup.find('article') or soup.find('div', role='main') or soup.body
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)  # Fallback to whole body
                
            # Clean up excessive whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)  # Collapse multiple blank lines
            text = text.strip()
            
            if len(text) > MAX_CONTENT_LENGTH:
                logger.info(f"Content truncated from {len(text)} to {MAX_CONTENT_LENGTH} characters for {url}")
                text = text[:MAX_CONTENT_LENGTH] + "... (content truncated)"
                
            if not text:
                return f"Successfully accessed URL {url}, but no significant text content found."
                
            return f"Content from {url}:\n\n{text}"
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout error while trying to access {url}")
            return f"Error: Timeout while trying to access {url}"
        except requests.exceptions.RequestException as e:
            logger.error(f"Error accessing {url}: {e}")
            status_code = getattr(e.response, 'status_code', None)
            if status_code:
                return f"Error: Failed to access {url}. Status code: {status_code}"
            else:
                return f"Error: Could not access {url}. Reason: {e}"
        except Exception as e:
            logger.error(f"Unexpected error accessing {url}: {e}", exc_info=True)
            return f"Error: An unexpected error occurred while accessing {url}: {e}"
