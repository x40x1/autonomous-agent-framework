import logging
from .base_tool import BaseTool

try:
    from pynput import keyboard  
    Controller = keyboard.Controller
    Key = keyboard.Key
except ImportError:
    Controller = None

logger = logging.getLogger(__name__)

class KeyboardControlTool(BaseTool):
    name = "keyboard_control"
    description = (
        "Simulates keyboard input control. "
        "Input is a dictionary with parameters: 'action' and 'keys'. "
        "For 'type', it types the given string. For 'press', it simulates pressing and releasing the specified key or keys."
    )
    
    def __init__(self):
        logger.info("KeyboardControlTool initialized.")
        if Controller is None:
            logger.error("pynput library is not installed. Install with: pip install pynput")
    
    def execute(self, command: dict) -> str:
        if Controller is None:
            return "Error: pynput library not available. Install with 'pip install pynput'."
        action = command.get("action")
        keys = command.get("keys")
        if not action or not keys:
            return "Error: 'action' and 'keys' parameters are required."
        keyboard = Controller()
        if action == "type":
            keyboard.type(keys)
            logger.info(f"Typed keys: {keys}")
            return f"Typed keys: {keys}"
        elif action == "press":
            try:
                if isinstance(keys, list):
                    for key in keys:
                        keyboard.press(key)
                        keyboard.release(key)
                else:
                    keyboard.press(keys)
                    keyboard.release(keys)
                logger.info(f"Pressed and released key(s): {keys}")
                return f"Pressed and released key(s): {keys}"
            except Exception as e:
                logger.error(f"Error during key press: {e}", exc_info=True)
                return f"Error during key press: {e}"
        else:
            return f"Error: Unknown action '{action}'. Use 'type' or 'press'."
