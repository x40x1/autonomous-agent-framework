import subprocess
import logging
import shlex
import os
from typing import List

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# WARNING: This tool is extremely dangerous if the agent is compromised or makes mistakes.
# It allows arbitrary command execution on the host system.

class CommandLineTool(BaseTool):
    name = "command_line"
    description = (
        "Executes a command line command on the host system's default shell. "
        "Input should be the command string (e.g., 'ls -l', 'echo hello'). "
        "Use with extreme caution. Returns the command's stdout and stderr."
    )
    is_dangerous: bool = True  # Mark as dangerous

    def __init__(self, enabled: bool = False, timeout: int = 60):
         """
         Initializes the CommandLineTool.
         Args:
             enabled: Explicit flag to enable this dangerous tool. Must be true to execute.
             timeout: Timeout in seconds for the command execution.
         """
         self.enabled = enabled
         self.timeout = timeout
         if not self.enabled:
             logger.warning("CommandLineTool initialized but DISABLED by configuration. It will not execute commands.")
         else:
             logger.critical("CommandLineTool initialized and ENABLED. The agent can run arbitrary shell commands. EXTREME DANGER.")

    def execute(self, command: str) -> str:
        """
        Executes the given command line command.

        Args:
            command: The command string to execute.

        Returns:
            A string containing the stdout and stderr of the command, or an error message.
        """
        if not self.enabled:
            return "Error: The command_line tool is disabled in the configuration for security reasons."

        if not command:
            return "Error: No command provided."

        logger.warning(f"Executing potentially dangerous command: '{command}'") # Log with warning level

        try:
            # Create a copy of the current environment and set PYTHONUNBUFFERED to "1" to force unbuffered output.
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            process = subprocess.run(
                command,
                shell=True,         # DANGER ZONE!
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,         # Don't raise CalledProcessError, capture return code instead
                env=env              # Pass the modified environment
            )

            output = f"Command executed: '{command}'\n"
            output += f"Return Code: {process.returncode}\n"
            if process.stdout:
                output += f"STDOUT:\n{process.stdout.strip()}\n"
            else:
                output += "STDOUT: (empty)\n"

            if process.stderr:
                 output += f"STDERR:\n{process.stderr.strip()}\n"
            else:
                 output += "STDERR: (empty)\n"

            if process.returncode != 0:
                 logger.warning(f"Command '{command}' exited with non-zero status: {process.returncode}")
                 # The output string already contains the details

            logger.info(f"Command '{command}' finished. Return code: {process.returncode}")
            # Limit output length to prevent overwhelming the LLM context
            if len(output) > 5000:
                 output = output[:5000] + "\n... (output truncated)"
            return output.strip()

        except subprocess.TimeoutExpired:
            logger.error(f"Command '{command}' timed out after {self.timeout} seconds.")
            return f"Error: Command '{command}' timed out after {self.timeout} seconds."
        except Exception as e:
            logger.error(f"Error executing command '{command}': {e}", exc_info=True)
            return f"Error executing command '{command}': {e}"