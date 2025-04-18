import os
import logging
import ast  # New import
from pathlib import Path
from typing import Union

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# Define a safe base directory (relative to the script's CWD or a specific workspace)
# This is a *minimal* safety measure. An "allmächtig" agent could still navigate out.
# For true "allmächtig", you might set this to None or '/', but that's extremely risky.
# Let's default to a 'workspace' subdirectory in the agent's run directory.
DEFAULT_WORKSPACE = Path("workspace")
DEFAULT_WORKSPACE.mkdir(exist_ok=True) # Ensure it exists

class FileSystemTool(BaseTool):
    name = "file_system"
    description = (
        "Performs file system operations like reading, writing, listing files and directories. "
        "Specify the operation ('read', 'write', 'list', 'mkdir', 'delete') and the path. "
        "Paths are relative to the agent's workspace directory. Use '.' for the current workspace dir. "
        "For 'write', provide 'path' and 'content'. For 'delete', provide 'path'."
    )
    is_dangerous: bool = True # Mark as dangerous (modifies file system)

    def __init__(self, base_directory: Union[str, Path, None] = DEFAULT_WORKSPACE):
        """
        Initializes the FileSystemTool.
        Args:
            base_directory: The root directory the agent is allowed to operate within.
                            If None, it operates from the current working directory (more risky).
        """
        if base_directory:
            self.base_path = Path(base_directory).resolve()
            logger.info(f"FileSystemTool initialized. Workspace: {self.base_path}")
        else:
            self.base_path = Path.cwd().resolve() # Use CWD if no base specified
            logger.warning(f"FileSystemTool initialized without a restricted base directory. Operating relative to CWD: {self.base_path}. THIS IS RISKY.")
        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)


    def _resolve_path(self, relative_path: str) -> Path:
        """Resolves a relative path against the base directory and checks bounds."""
        # Clean the input path (handle '..', '.', etc.)
        requested_path = Path(relative_path).resolve() # First resolve normally based on CWD

        # Then make it relative to base_path IF relative_path didn't escape CWD significantly
        # This logic is tricky. A simpler, safer way is to directly join with base_path.
        # Let's enforce that: paths are *always* interpreted relative to base_path.
        resolved_path = self.base_path.joinpath(relative_path).resolve()


        # **Security Check**: Ensure the resolved path is still within the base directory.
        # This is crucial to prevent the agent escaping its workspace.
        if self.base_path not in resolved_path.parents and resolved_path != self.base_path:
             # Allow access to the base path itself, but not parents
             logger.error(f"Path traversal attempt detected: '{relative_path}' resolved to '{resolved_path}', which is outside the allowed base '{self.base_path}'")
             raise PermissionError(f"Access denied: Path '{relative_path}' is outside the allowed workspace.")

        return resolved_path


    def execute(self, operation: str, path: str = ".", content: str = None) -> str:
        """
        Executes a file system operation.

        Args:
            operation: The action to perform ('read', 'write', 'list', 'mkdir', 'delete').
            path: The relative path within the workspace.
            content: The content to write (only for 'write' operation).

        Returns:
            A string describing the result or an error message.
        """
        try:
            # New: Check if operation looks like a dict string, and if so, parse it.
            if operation.strip().startswith("{") and operation.strip().endswith("}"):
                try:
                    parsed = ast.literal_eval(operation)
                    if isinstance(parsed, dict):
                        operation = parsed.get("operation", "").lower()
                        path = parsed.get("path", path)
                        content = parsed.get("content", content)
                    else:
                        return "Error: Invalid operation format."
                except Exception as e:
                    return f"Error parsing operation input: {e}"
            else:
                operation = operation.lower()

            target_path = self._resolve_path(path)
            logger.info(f"Executing file system operation '{operation}' on path '{target_path}' (relative: '{path}')")


            if operation == "read":
                if not target_path.is_file():
                    return f"Error: Path '{path}' does not exist or is not a file."
                try:
                    # Limit read size? For now, read all. Add limit if needed.
                    file_content = target_path.read_text(encoding='utf-8', errors='ignore')
                    # Be careful returning large files directly to the LLM context
                    if len(file_content) > 5000:
                        return f"Successfully read file '{path}'. Content (truncated):\n{file_content[:5000]}..."
                    return f"Successfully read file '{path}'. Content:\n{file_content}"
                except Exception as e:
                    logger.error(f"Error reading file {target_path}: {e}")
                    return f"Error reading file '{path}': {e}"

            elif operation == "write":
                if content is None:
                    return "Error: Content must be provided for 'write' operation."
                try:
                    # Ensure parent directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_text(content, encoding='utf-8')
                    logger.info(f"Successfully wrote {len(content)} characters to {target_path}")
                    return f"Successfully wrote content to file '{path}'."
                except Exception as e:
                    logger.error(f"Error writing file {target_path}: {e}")
                    return f"Error writing file '{path}': {e}"

            elif operation == "list":
                if not target_path.is_dir():
                    return f"Error: Path '{path}' does not exist or is not a directory."
                try:
                    items = list(target_path.iterdir())
                    if not items:
                        return f"Directory '{path}' is empty."
                    else:
                        item_list = "\n".join([f"- {'[D] ' if item.is_dir() else '[F] '}{item.name}" for item in items])
                        return f"Contents of directory '{path}':\n{item_list}"
                except Exception as e:
                    logger.error(f"Error listing directory {target_path}: {e}")
                    return f"Error listing directory '{path}': {e}"

            elif operation == "mkdir":
                if target_path.exists() and target_path.is_dir():
                     return f"Directory '{path}' already exists."
                elif target_path.exists():
                     return f"Error: Path '{path}' exists but is not a directory."
                try:
                    target_path.mkdir(parents=True, exist_ok=True) # exist_ok=True makes it idempotent if dir exists
                    logger.info(f"Successfully created directory {target_path}")
                    return f"Successfully created directory '{path}'."
                except Exception as e:
                    logger.error(f"Error creating directory {target_path}: {e}")
                    return f"Error creating directory '{path}': {e}"

            elif operation == "delete":
                 if not target_path.exists():
                     return f"Error: Path '{path}' does not exist."
                 try:
                     if target_path.is_file():
                         target_path.unlink()
                         logger.info(f"Successfully deleted file {target_path}")
                         return f"Successfully deleted file '{path}'."
                     elif target_path.is_dir():
                          # For safety, let's prevent recursive deletion by default.
                          # The agent would need to list contents and delete files first.
                          # If you *want* recursive delete, add `shutil.rmtree(target_path)`
                          # BUT THAT IS VERY DANGEROUS WITH AN AUTONOMOUS AGENT.
                          # We will only allow deleting empty directories for now.
                          if not list(target_path.iterdir()):
                              target_path.rmdir()
                              logger.info(f"Successfully deleted empty directory {target_path}")
                              return f"Successfully deleted empty directory '{path}'."
                          else:
                              logger.warning(f"Attempted to delete non-empty directory {target_path}. Denied for safety.")
                              return f"Error: Directory '{path}' is not empty. Cannot delete non-empty directories."
                     else:
                          return f"Error: Path '{path}' is neither a file nor a directory."

                 except Exception as e:
                     logger.error(f"Error deleting path {target_path}: {e}")
                     return f"Error deleting path '{path}': {e}"


            else:
                return f"Error: Unknown file system operation '{operation}'. Valid operations: read, write, list, mkdir, delete."

        except PermissionError as e:
             # Catch the specific error from _resolve_path
             return f"Error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error in FileSystemTool for operation '{operation}', path '{path}': {e}", exc_info=True)
            return f"Error during file system operation '{operation}' on '{path}': {e}"