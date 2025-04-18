import logging
from typing import Any, Dict, List
import requests # Use requests for Ollama's HTTP API
import json
import time

from .base_llm import BaseLLM

logger = logging.getLogger(__name__)

class OllamaLLM(BaseLLM):
    """Interface for local LLMs served via Ollama."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config.get('ollama', {})) # Pass only ollama sub-config
        self.host = self.config.get('host', 'http://localhost:11434')
        self.model = self.config.get('model')
        if not self.model:
            raise ValueError("Ollama model name is required but not found in config.")

        self.api_url = f"{self.host}/api/generate"
        # Ensure self.options is a dict, even if config['options'] is None
        self.options = self.config.get('options') or {}
        if 'temperature' in self.config:
            # Check if self.config['temperature'] exists before assigning
            temp = self.config.get('temperature')
            if temp is not None:
                self.options['temperature'] = temp
        # Ollama uses 'stop' within options
        # self.stop_sequences = None # We'll pass stop sequences per request

        logger.info(f"Initialized OllamaLLM with model: {self.model} at host: {self.host}")
        self._check_connection()


    def _check_connection(self):
        """Checks if the Ollama server is reachable."""
        try:
            response = requests.head(self.host, timeout=5)
            response.raise_for_status() # Raise exception for bad status codes
            logger.info(f"Successfully connected to Ollama server at {self.host}")
            # Optionally check if the specific model is available
            try:
                models_res = requests.get(f"{self.host}/api/tags")
                models_res.raise_for_status()
                available_models = [m['name'] for m in models_res.json().get('models', [])]
                # Check if the base model name (e.g., "llama3" without ":latest") is present
                base_model_name = self.model.split(':')[0]
                if not any(base_model_name in m for m in available_models):
                     logger.warning(f"Model '{self.model}' (or base '{base_model_name}') not found in available models on Ollama server: {available_models}. Make sure you have pulled it.")
                else:
                    logger.info(f"Model '{self.model}' appears to be available on the Ollama server.")
            except requests.RequestException as e:
                 logger.warning(f"Could not verify model list from Ollama server: {e}")

        except requests.ConnectionError:
            logger.error(f"Connection Error: Could not connect to Ollama server at {self.host}. Is Ollama running?")
            raise ConnectionError(f"Could not connect to Ollama server at {self.host}")
        except requests.Timeout:
             logger.error(f"Timeout: Connection to Ollama server at {self.host} timed out.")
             raise TimeoutError(f"Connection to Ollama server at {self.host} timed out.")
        except requests.RequestException as e:
            logger.error(f"Error connecting to Ollama server at {self.host}: {e}")
            raise ConnectionError(f"Error connecting to Ollama server: {e}")


    def generate(self, prompt: str, stop: List[str] = None) -> str:
        """
        Generates text using the Ollama API.

        Args:
            prompt: The input text prompt.
            stop: List of stop sequences. Passed in the request payload.

        Returns:
            The generated text response.
        """
        if stop is None:
            stop = ["\nObservation:"] # Default stop sequence for ReAct

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False, # Get the full response at once
            "options": self.options.copy() # Start with base options
        }
        if stop:
             payload["options"]["stop"] = stop # Add stop sequences if provided


        retries = 3
        delay = 5
        for attempt in range(retries):
            try:
                logger.debug(f"--- Sending prompt to Ollama ({self.model}) ---")
                # logger.debug(f"Prompt:\n{prompt}") # Careful logging prompts
                logger.debug(f"Stop sequences: {stop}")
                logger.debug(f"Options: {payload['options']}")
                logger.debug("--- End of Prompt ---")

                response = requests.post(self.api_url, json=payload, timeout=120) # Increased timeout for potentially slow local models
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

                response_data = response.json()
                generated_text = response_data.get('response', '').strip()

                # Log usage/context info if available (depends on Ollama version)
                eval_count = response_data.get('eval_count')
                eval_duration = response_data.get('eval_duration')
                if eval_count and eval_duration:
                    eval_sec = eval_duration / 1_000_000_000 # Nanoseconds to seconds
                    tokens_per_sec = eval_count / eval_sec if eval_sec > 0 else float('inf')
                    logger.debug(f"Ollama generation stats: {eval_count} tokens, {eval_sec:.2f}s ({tokens_per_sec:.2f} t/s)")


                logger.debug(f"--- Received response from Ollama ---")
                logger.debug(f"Response:\n{generated_text}")
                logger.debug(f"--- End of Response ---")
                return generated_text

            except requests.ConnectionError as e:
                 logger.error(f"Ollama Connection Error: {e}. Is Ollama running? Retrying in {delay}s... (Attempt {attempt + 1}/{retries})")
                 time.sleep(delay)
                 delay *= 2
            except requests.Timeout as e:
                 logger.warning(f"Ollama request timed out: {e}. Retrying in {delay}s... (Attempt {attempt + 1}/{retries})")
                 time.sleep(delay)
                 delay *= 2
            except requests.RequestException as e:
                 logger.error(f"Ollama API request failed: {e}", exc_info=True)
                 # Check if it's potentially recoverable or a model issue
                 if response.status_code == 404:
                      logger.error(f"Model '{self.model}' not found on Ollama server. Please ensure it's pulled.")
                      raise # Don't retry if model not found
                 if response.status_code >= 500:
                      logger.warning(f"Ollama server error ({response.status_code}). Retrying in {delay}s... (Attempt {attempt + 1}/{retries})")
                      time.sleep(delay)
                      delay *= 2
                 else: # Likely client error (4xx) other than 404
                     logger.error(f"Unhandled Ollama client error ({response.status_code}). Aborting.")
                     raise # Don't retry other client errors usually
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON response from Ollama: {e}. Response text: {response.text}", exc_info=True)
                raise # Cannot proceed if response is not valid JSON
            except Exception as e:
                logger.error(f"An unexpected error occurred during Ollama API call: {e}", exc_info=True)
                raise # Re-raise unexpected errors

        logger.error("Failed to get response from Ollama after multiple retries.")
        return "Error: Could not get response from Ollama API."