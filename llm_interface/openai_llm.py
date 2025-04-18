import logging
from typing import Any, Dict, List
from openai import OpenAI, APIError, RateLimitError, APITimeoutError
import time

from .base_llm import BaseLLM

logger = logging.getLogger(__name__)

class OpenAILLM(BaseLLM):
    """Interface for OpenAI's GPT models."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config.get('openai', {})) # Pass only openai sub-config
        self.api_key = self.config.get('api_key')
        if not self.api_key:
            # Should have been checked in config loading, but double-check
            raise ValueError("OpenAI API key is required but not found in config or environment.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = self.config.get('model', 'gpt-3.5-turbo')
        self.temperature = self.config.get('temperature', 0.7)
        self.max_tokens = self.config.get('max_tokens', 1000)
        logger.info(f"Initialized OpenAILLM with model: {self.model}")

    def generate(self, prompt: str, stop: List[str] = None) -> str:
        """
        Generates text using the OpenAI API with retry logic.

        Args:
            prompt: The input text prompt.
            stop: List of stop sequences. OpenAI API uses 'stop'.

        Returns:
            The generated text response.
        """
        if stop is None:
            # Default stop sequence for ReAct format to encourage completion
            stop = ["\nObservation:"]

        retries = 3
        delay = 5  # seconds
        for attempt in range(retries):
            try:
                logger.debug(f"--- Sending prompt to OpenAI ({self.model}) ---")
                # logger.debug(f"Prompt:\n{prompt}") # Be careful logging full prompts if sensitive
                logger.debug(f"Stop sequences: {stop}")
                logger.debug(f"Max tokens: {self.max_tokens}, Temperature: {self.temperature}")
                logger.debug("--- End of Prompt ---")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stop=stop,
                    # top_p=1, # Adjust other parameters as needed
                    # frequency_penalty=0,
                    # presence_penalty=0
                )

                generated_text = response.choices[0].message.content.strip()
                logger.debug(f"--- Received response from OpenAI ---")
                logger.debug(f"Response:\n{generated_text}")
                logger.debug(f"--- End of Response ---")
                return generated_text

            except RateLimitError as e:
                logger.warning(f"OpenAI RateLimitError: {e}. Retrying in {delay}s... (Attempt {attempt + 1}/{retries})")
                time.sleep(delay)
                delay *= 2 # Exponential backoff
            except APITimeoutError as e:
                 logger.warning(f"OpenAI APITimeoutError: {e}. Retrying in {delay}s... (Attempt {attempt + 1}/{retries})")
                 time.sleep(delay)
                 delay *= 2
            except APIError as e:
                logger.error(f"OpenAI APIError: {e}. Check your API key and network connection.")
                # Depending on the error type, retry might not help (e.g., auth error)
                # For now, we break after API errors that aren't rate limits/timeouts
                if attempt == retries - 1:
                    raise # Re-raise the last exception if all retries fail
                else:
                     logger.warning(f"Retrying after API error (Attempt {attempt + 1}/{retries})...")
                     time.sleep(delay) # Still wait before retrying
            except Exception as e:
                logger.error(f"An unexpected error occurred during OpenAI API call: {e}", exc_info=True)
                raise # Re-raise unexpected errors immediately

        logger.error("Failed to get response from OpenAI after multiple retries.")
        return "Error: Could not get response from OpenAI API." # Return error message if all retries fail