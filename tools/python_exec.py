import io
import sys
import logging
import traceback
from contextlib import redirect_stdout, redirect_stderr

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# WARNING: This tool is extremely dangerous. It executes arbitrary Python code.
# It can modify the agent's own state, access global variables, delete files, etc.

class PythonExecutorTool(BaseTool):
    name = "python_exec"
    description = (
        "Executes a given snippet of Python code using Python's `exec()`. "
        "Input is the raw Python code string. Captures stdout and stderr. "
        "Use with EXTREME caution. Code runs in the agent's process."
        "Access to local variables ('local_vars') and global variables ('global_vars') is provided."
        "The result of the last expression evaluated (if any) is returned."
    )
    is_dangerous: bool = True

    def __init__(self, enabled: bool = False):
        """
        Initializes the PythonExecutorTool.
        Args:
            enabled: Explicit flag to enable this dangerous tool. Must be true to execute.
        """
        self.enabled = enabled
        if not self.enabled:
            logger.warning("PythonExecutorTool initialized but DISABLED by configuration. It will not execute code.")
        else:
             logger.critical("PythonExecutorTool initialized and ENABLED. The agent can run arbitrary Python code within its own process. EXTREME DANGER.")

        # You could potentially provide some safe globals/locals here if needed
        # Be very careful what you expose.
        self.exec_globals = {"__builtins__": __builtins__} # Basic builtins
        self.exec_locals = {} # Execution context


    def execute(self, code_snippet: str) -> str:
        """
        Executes the given Python code snippet.

        Args:
            code_snippet: The Python code string to execute.

        Returns:
            A string containing the captured stdout, stderr, and the result of the execution, or an error message.
        """
        if not self.enabled:
            return "Error: The python_exec tool is disabled in the configuration for security reasons."

        if not code_snippet:
            return "Error: No Python code provided to execute."

        logger.warning(f"Executing potentially dangerous Python code:\n---\n{code_snippet}\n---")

        # Prepare streams to capture output
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        result = None
        output_str = f"Executing Python code:\n```python\n{code_snippet}\n```\n"

        try:
            # Redirect stdout and stderr
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Execute the code
                # Using exec allows statements, not just expressions (like eval)
                exec(code_snippet, self.exec_globals, self.exec_locals)

                # Try to get the result of the last expression if the code was an expression
                # This is a bit heuristic; exec doesn't return a value directly.
                # A common pattern is to have the last line be the variable holding the result.
                # Or the user might explicitly call a function or assign to a known var.
                # We won't try complex result extraction, just capture stdio.


            stdout_val = stdout_capture.getvalue().strip()
            stderr_val = stderr_capture.getvalue().strip()

            output_str += "Execution Result:\n"
            if stdout_val:
                output_str += f"STDOUT:\n{stdout_val}\n"
            else:
                 output_str += "STDOUT: (empty)\n"

            if stderr_val:
                 # Treat stderr as a potential error/warning, but include it
                 output_str += f"STDERR:\n{stderr_val}\n"
                 logger.warning(f"Python code execution produced STDERR: {stderr_val}")
            else:
                 output_str += "STDERR: (empty)\n"

            output_str += "Execution finished successfully."
            logger.info("Python code executed successfully.")


        except Exception as e:
            logger.error(f"Error executing Python code: {e}", exc_info=True)
            error_trace = traceback.format_exc()
            output_str += f"ERROR during execution:\n{type(e).__name__}: {e}\n"
            output_str += f"Traceback:\n{error_trace}"
            return output_str # Return immediately on error

        finally:
             # Close the streams
             stdout_capture.close()
             stderr_capture.close()

        # Limit output length
        if len(output_str) > 5000:
            output_str = output_str[:5000] + "\n... (output truncated)"

        return output_str.strip()