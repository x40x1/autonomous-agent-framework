import logging
from typing import List, Dict, Type, Optional, Any
import os
import importlib
import inspect
from pathlib import Path
import sys

from .base_tool import BaseTool
from .web_search import WebSearchTool
from .file_system import FileSystemTool
from .command_line import CommandLineTool
from .python_exec import PythonExecutorTool
from .open_url import OpenURLTool
from .database_tool import DatabaseTool
from .keyboard_control_tool import KeyboardControlTool

# Tier 1 Tools
from .browser_automation_tool import BrowserAutomationTool
from .human_input_tool import HumanInputTool

# Tier 2 Tools
from .screen_reader_tool import ScreenReaderTool

# Tier 3 Tools
from .code_modifier_tool import CodeModifierTool
from .task_spawner_tool import TaskSpawnerTool

logger = logging.getLogger(__name__)

# Map tool names to classes for easier management (optional but helpful)
_TOOL_CLASSES: Dict[str, Type[BaseTool]] = {
    "web_search": WebSearchTool,
    "file_system": FileSystemTool,
    "open_url": OpenURLTool,
    "database": DatabaseTool,
    "browser_automation": BrowserAutomationTool,
    "ask_human": HumanInputTool,
    "read_screen": ScreenReaderTool,
    "command_line": CommandLineTool,
    "python_exec": PythonExecutorTool,
    "code_modifier": CodeModifierTool,
    "task_spawner": TaskSpawnerTool,
    "keyboard_control": KeyboardControlTool,
}

def get_tool_descriptions(tools: List[BaseTool]) -> str:
    """Formats the descriptions of available tools for the LLM prompt."""
    if not tools:
        return "No tools available."
    return "\n".join([f"- {tool.get_description()}" for tool in tools])

def get_tool_names(tools: List[BaseTool]) -> List[str]:
    """Gets a list of names of available tools."""
    return [tool.name for tool in tools]

def get_available_tools(config: Dict) -> List[BaseTool]:
    """
    Initializes and returns a list of available tools based on the configuration,
    including dynamically loaded plugins. Tools determine their dangerous status
    via an 'is_dangerous' class attribute.
    """
    available_tools: List[BaseTool] = []
    initialized_tool_names = set()  # Keep track of names to avoid duplicates

    # Determine if dangerous tools are globally enabled
    enable_dangerous = config.get('enable_dangerous_tools', False)
    if enable_dangerous:
        logger.critical("DANGEROUS TOOLS ARE GLOBALLY ENABLED IN CONFIGURATION.")
    else:
        logger.info("Dangerous tools are globally disabled. Tools with 'is_dangerous=True' in their code will be skipped.")

    # --- Instantiate Built-in Tools ---
    logger.debug("Instantiating built-in tools...")
    tools_config = config.get('tools', {})

    def _instantiate_tool(tool_name: str, tool_class: Type[BaseTool], specific_config: Dict):
        nonlocal available_tools, initialized_tool_names
        if tool_name in initialized_tool_names:
            logger.warning(f"Tool '{tool_name}' already initialized. Skipping duplicate.")
            return

        is_dangerous_in_code = getattr(tool_class, 'is_dangerous', False)
        
        # Only instantiate dangerous tools if globally enabled
        if is_dangerous_in_code and not config.get('enable_dangerous_tools', False):
            logger.info(f"Skipping dangerous tool '{tool_name}' because dangerous tools are globally disabled.")
            return

        try:
            tool_instance = None
            # --- Tool-specific instantiation logic ---
            if tool_name == "web_search":
                tool_instance = tool_class(
                    num_results=specific_config.get('num_results', 10),
                    num_results_to_scrape=specific_config.get('num_results_to_scrape', 3),
                    lang=specific_config.get('lang', 'en'),
                    region=specific_config.get('region'),
                    safe=specific_config.get('safe', 'on'),
                    sleep_interval=specific_config.get('sleep_interval', 0)
                )
            elif tool_name == "file_system":
                tool_instance = tool_class(base_directory=specific_config.get('base_directory', 'workspace'))
            elif tool_name == "open_url":
                tool_instance = tool_class()
            elif tool_name == "database":
                tool_instance = tool_class(
                    connection_strings=specific_config.get('connection_strings', {"default": "sqlite:///workspace/agent.db"}),
                    max_results=specific_config.get('max_results', 100)
                )
            elif tool_name == "browser_automation":
                tool_instance = tool_class(timeout=specific_config.get('timeout', 30000))
            elif tool_name == "ask_human":
                tool_instance = tool_class()
            elif tool_name == "screen_reader":
                tool_instance = tool_class(tesseract_cmd=specific_config.get('tesseract_cmd'))
            elif tool_name == "command_line":
                tool_instance = tool_class(enabled=True, timeout=specific_config.get('timeout', 60))
            elif tool_name == "python_exec":
                tool_instance = tool_class(enabled=True)
            elif tool_name == "code_modifier":
                if not isinstance(specific_config, dict):
                    specific_config = {}
                tool_instance = tool_class(enabled=True, project_root=specific_config.get('project_root'))
            elif tool_name == "task_spawner":
                tool_instance = tool_class()
            else:
                logger.warning(f"No specific instantiation logic for built-in tool '{tool_name}'. Using default __init__().")
                tool_instance = tool_class()

            if tool_instance:
                danger_status = "DANGEROUS" if is_dangerous_in_code else "Standard"
                logger.info(f"Successfully instantiated tool: {tool_name} ({danger_status})")
                available_tools.append(tool_instance)
                initialized_tool_names.add(tool_name)

        except Exception as e:
            logger.error(f"Failed to instantiate tool '{tool_name}': {e}", exc_info=True)

    for tool_name, tool_class in _TOOL_CLASSES.items():
        specific_config = tools_config.get(tool_name, {})
        _instantiate_tool(tool_name, tool_class, specific_config)

    # --- Load Enabled Plugins ---
    logger.debug("Loading enabled plugins...")
    plugin_config = config.get('plugins', {})
    enabled_plugins = plugin_config.get('enabled', [])
    plugins_dir = Path("plugins")

    if not plugins_dir.is_dir():
        logger.info("Plugins directory 'plugins/' not found. Skipping plugin loading.")
    elif not enabled_plugins:
        logger.info("No plugins enabled in config.yaml.")
    else:
        logger.info(f"Attempting to load enabled plugins: {enabled_plugins}")
        for plugin_name in enabled_plugins:
            plugin_path = plugins_dir / plugin_name
            if not plugin_path.is_dir():
                logger.warning(f"Enabled plugin '{plugin_name}' directory not found at {plugin_path}. Skipping.")
                continue

            logger.info(f"Loading plugin: {plugin_name}")
            try:
                sys.path.insert(0, str(plugin_path.resolve()))

                for py_file in plugin_path.glob('*.py'):
                    module_name = py_file.stem
                    try:
                        module = importlib.import_module(module_name)

                        for name, obj in inspect.getmembers(module):
                            if inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                                tool_class = obj
                                tool_instance_name = getattr(tool_class, 'name', tool_class.__name__.lower())

                                if tool_instance_name in initialized_tool_names:
                                    logger.warning(f"Tool '{tool_instance_name}' from plugin '{plugin_name}' conflicts with an already loaded tool. Skipping.")
                                    continue

                                is_dangerous_in_code = getattr(tool_class, 'is_dangerous', False)
                                if is_dangerous_in_code and not enable_dangerous:
                                    logger.info(f"Skipping dangerous plugin tool '{tool_instance_name}' from '{plugin_name}' because its class defines 'is_dangerous=True' and dangerous tools are globally disabled.")
                                    continue

                                try:
                                    plugin_specific_config = tools_config.get(plugin_name, {}).get(tool_instance_name, {})
                                    tool_instance = tool_class()
                                    danger_status = "DANGEROUS" if is_dangerous_in_code else "Standard"
                                    logger.info(f"Successfully instantiated plugin tool: {tool_instance_name} from {plugin_name} ({danger_status})")
                                    available_tools.append(tool_instance)
                                    initialized_tool_names.add(tool_instance_name)
                                except Exception as e_init:
                                    logger.error(f"Failed to instantiate plugin tool '{tool_instance_name}' from {plugin_name}: {e_init}", exc_info=True)

                    except ImportError as e_import:
                        logger.error(f"Failed to import module '{module_name}' from plugin '{plugin_name}': {e_import}", exc_info=True)
                    except Exception as e_scan:
                        logger.error(f"Error scanning file '{py_file}' in plugin '{plugin_name}': {e_scan}", exc_info=True)

                sys.path.pop(0)

            except Exception as e_plugin:
                logger.error(f"Failed to load plugin '{plugin_name}': {e_plugin}", exc_info=True)
                if str(plugin_path.resolve()) in sys.path:
                    sys.path.remove(str(plugin_path.resolve()))

    logger.info(f"Initialized {len(available_tools)} tools: {initialized_tool_names}")
    return available_tools