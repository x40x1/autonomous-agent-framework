import logging

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

class HumanInputTool(BaseTool):
    name = "ask_human"
    description = (
        "Asks the user running the agent for input or clarification. "
        "Execution pauses until the user provides input via the command line. "
        "Input is the prompt string to display to the user. "
        "Returns the user's response as a string."
    )

    def __init__(self):
        logger.info("HumanInputTool initialized.")
        # TODO: Consider how this interacts with Streamlit UI if needed.
        # Streamlit requires different mechanisms (e.g., st.text_input with callbacks or session state).
        # This implementation is primarily for CLI execution (main.py).

    def execute(self, prompt: str) -> str:
        """
        Prompts the user for input on the command line.

        Args:
            prompt: The question or instruction to display to the user.

        Returns:
            The text entered by the user.
        """
        if not prompt:
            prompt = "Agent requires input:"

        logger.info(f"Asking human for input. Prompt: '{prompt}'")

        # Print clearly separated prompt for the user
        print("\n" + "="*20 + " AGENT REQUIRES HUMAN INPUT " + "="*20)
        print(f"Prompt: {prompt}")
        print("Please type your response below and press Enter:")
        print("="*60)

        try:
            user_response = input("> ")
            logger.info(f"Received human input: '{user_response}'")
            print("="*60 + "\n") # Add separator after input
            return f"Human response to '{prompt}': {user_response}"
        except EOFError:
            # Handle cases where input stream is closed (e.g., piping input)
            logger.warning("EOFError received while waiting for human input. Returning empty response.")
            print("="*60 + "\n")
            return "Human response: (No input received - EOF)"
        except KeyboardInterrupt:
             logger.warning("KeyboardInterrupt received while waiting for human input. Returning empty response.")
             print("\n" + "="*60 + "\n")
             # Re-raise? Or return specific signal? For now, return indication.
             return "Human response: (Interrupted by user)"