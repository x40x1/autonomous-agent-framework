import logging
import os
from pathlib import Path
from typing import Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# WARNING: EXTREMELY DANGEROUS TOOL. Allows the agent to modify its own code or other files.
# Potential for self-destruction, infinite loops, security holes, or system damage.

class CodeModifierTool(BaseTool):
    name = "code_modifier"
    description = (
        "Reads or writes to files, intended for modifying the agent's own code or related files. "
        "USE WITH EXTREME CAUTION AND ONLY IF ABSOLUTELY NECESSARY. "
        "Input: {'action': 'read'|'write', 'file_path': 'relative/path/to/file.py', 'content': '(for write action)'}. "
        "Paths MUST be relative to the agent's root directory. "
        "Prevents modification outside the project directory by default."
    )
    is_dangerous: bool = True

    def __init__(self, enabled: bool = False, project_root: Optional[str] = None):
        """
        Initializes the CodeModifierTool.
        Args:
            enabled: Explicit flag to enable this dangerous tool.
            project_root: The absolute path to the agent's project root directory. If None, determined automatically.
        """
        self.enabled = enabled
        if not self.enabled:
            logger.warning("CodeModifierTool initialized but DISABLED by configuration. It will not read or write code.")
            self.project_root = None
            return

        if project_root:
             self.project_root = Path(project_root).resolve()
        else:
             # Try to determine project root automatically (assuming tool is in tools/ dir)
             self.project_root = Path(__file__).parent.parent.resolve()

        logger.critical(f"CodeModifierTool initialized and ENABLED. Project Root constrained to: '{self.project_root}'. EXTREME DANGER.")


    def _resolve_and_validate_path(self, relative_path_str: str) -> Path:
        """Resolves the path relative to project root and validates it."""
        if not self.project_root:
             raise EnvironmentError("Project root not set for CodeModifierTool.")

        # Clean the input path first (handle '.', '..') relative to project root
        target_path = self.project_root.joinpath(relative_path_str).resolve()

        # **Security Check**: Ensure the resolved path is within the project root directory.
        if self.project_root not in target_path.parents and target_path != self.project_root:
            logger.error(f"Path traversal attempt denied: '{relative_path_str}' resolved to '{target_path}', which is outside the project root '{self.project_root}'.")
            raise PermissionError(f"Access denied: Path '{relative_path_str}' is outside the allowed project directory.")

        # Optional: Add checks for specific sensitive files/directories (e.g., .git, .env)
        # if '.git' in target_path.parts or target_path.name == '.env':
        #     logger.warning(f"Attempting to access sensitive path: {target_path}")
            # raise PermissionError("Access to sensitive paths like .git or .env might be restricted.")

        return target_path

    def execute(self, **kwargs) -> str:
        if not self.enabled:
            return "Error: The code_modifier tool is disabled in the configuration."

        action = kwargs.get('action')
        relative_path = kwargs.get('file_path')
        content = kwargs.get('content') # Only for write

        if not action or action.lower() not in ['read', 'write']:
            return "Error: Invalid or missing 'action'. Must be 'read' or 'write'."
        if not relative_path:
            return "Error: Missing 'file_path' parameter."

        action = action.lower()
        logger.warning(f"Executing Code Modifier action: {action} on path: '{relative_path}' relative to '{self.project_root}'")


        try:
            target_path = self._resolve_and_validate_path(relative_path)

            if action == 'read':
                if not target_path.is_file():
                    return f"Error: File not found at '{relative_path}'."
                try:
                    file_content = target_path.read_text(encoding='utf-8')
                    # Limit output length?
                    max_len = 10000
                    if len(file_content) > max_len:
                         file_content = file_content[:max_len] + f"\n... (content truncated to {max_len} chars)"
                    logger.info(f"Read {len(file_content)} chars from {target_path}")
                    return f"Content of '{relative_path}':\n```\n{file_content}\n```"
                except Exception as e:
                    logger.error(f"Error reading file {target_path}: {e}", exc_info=True)
                    return f"Error reading file '{relative_path}': {e}"

            elif action == 'write':
                if content is None:
                    return "Error: 'content' parameter missing for 'write' action."
                try:
                    # Ensure parent directory exists within the project
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    # Validate again after potential mkdir
                    if self.project_root not in target_path.parent.resolve().parents and target_path.parent.resolve() != self.project_root:
                         raise PermissionError("Parent directory creation would be outside project root.")

                    target_path.write_text(content, encoding='utf-8')
                    logger.critical(f"Successfully WROTE {len(content)} characters to potentially sensitive file: {target_path}") # Use critical log level
                    return f"Successfully wrote content to file '{relative_path}'."
                except Exception as e:
                    logger.error(f"Error writing file {target_path}: {e}", exc_info=True)
                    return f"Error writing file '{relative_path}': {e}"

        except PermissionError as e:
             # Catch the specific error from validation
             return f"Error: {e}"
        except EnvironmentError as e:
             return f"Error: Tool configuration issue - {e}"
        except Exception as e:
            logger.error(f"Unexpected error in CodeModifierTool for action '{action}', path '{relative_path}': {e}", exc_info=True)
            return f"Error during code_modifier operation '{action}' on '{relative_path}': {e}"