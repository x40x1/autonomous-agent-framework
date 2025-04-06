import logging
from typing import Any, Dict, List
import time
from google import genai
from google.genai import types  # Newly added import

from .base_llm import BaseLLM

logger = logging.getLogger(__name__)

# Convert default safety settings to a list of SafetySetting objects as per documentation
DEFAULT_SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE
    ),
]


class GeminiLLM(BaseLLM):
    """Interface for Google's Gemini models using the Client API."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config.get('gemini', {}))  # Pass only gemini sub-config
        self.api_key = self.config.get('api_key')
        if not self.api_key:
            raise ValueError("Google API key (GOOGLE_API_KEY) is required but not found in config or environment.")

        # Instantiate the client using the genai module
        try:
            self.client = genai.Client(api_key=self.api_key)  # Use genai.Client
        except Exception as e:
            logger.error(f"Failed to create Google AI Client: {e}", exc_info=True)
            raise ConnectionError(f"Failed to create Google AI Client: {e}")

        self.model_name = self.config.get('model', 'gemini-1.5-flash-latest')  # Default to a common model
        # Store generation parameters (keep these separate for constructing the config object later)
        self.temperature = self.config.get('temperature', 0.7)
        self.max_tokens = self.config.get('max_output_tokens')
        self.top_p = self.config.get('top_p')
        self.top_k = self.config.get('top_k')
        self.safety_settings_config = self.config.get('safety_settings', DEFAULT_SAFETY_SETTINGS)

        # Update _parse_safety_settings to return a list of SafetySetting objects
        self.safety_settings = self._parse_safety_settings(self.safety_settings_config)

        # Verify model availability (optional but good practice)
        try:
            logger.info(f"Initialized GeminiLLM with model: {self.model_name}")
        except Exception as e:
            logger.warning(f"Could not verify model list: {e}")
            # Continue initialization even if model list check fails

    def _parse_safety_settings(self, settings_config: Any) -> List[Any]:
        """Converts safety settings from config into a list of SafetySetting objects."""
        if isinstance(settings_config, list):
            return settings_config
        if isinstance(settings_config, dict):
            safety_list = []
            for key, value in settings_config.items():
                try:
                    safety_list.append(
                        types.SafetySetting(
                            category=getattr(types.HarmCategory, key),
                            threshold=getattr(types.HarmBlockThreshold, value)
                        )
                    )
                except AttributeError as e:
                    logger.warning(f"Invalid safety setting key or value: {e}. Skipping this entry.")
            return safety_list if safety_list else DEFAULT_SAFETY_SETTINGS
        return DEFAULT_SAFETY_SETTINGS

    def generate(self, prompt: str, stop: List[str] = None) -> str:
        """
        Generates text using the Gemini Client API with retry logic, following documentation style.
        Uses the 'config' parameter with a types.GenerateContentConfig object.
        """
        if stop is None:
            stop = ["\nObservation:"]

        # Construct the configuration dictionary including safety_settings
        generation_config_dict = {
            "temperature": self.temperature,
            **({"max_output_tokens": self.max_tokens} if self.max_tokens is not None else {}),
            **({"top_p": self.top_p} if self.top_p is not None else {}),
            **({"top_k": self.top_k} if self.top_k is not None else {}),
            **({"stop_sequences": stop} if stop else {}),
            "safety_settings": self.safety_settings  # Safety settings now go inside config
        }
        current_generation_config = types.GenerateContentConfig(**generation_config_dict)

        retries = 3
        delay = 5  # seconds
        for attempt in range(retries):
            try:
                logger.debug(f"--- Sending prompt to Gemini ({self.model_name}) ---")
                logger.debug(f"Generation Config: {generation_config_dict}")  # Log the dict form
                logger.debug("--- End of Prompt ---")

                # Updated call: pass 'config' rather than generation_config and remove separate safety_settings
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt],
                    config=current_generation_config
                )

                # Check for safety blocks before accessing text
                if not response.candidates:
                    block_reason = response.prompt_feedback.block_reason.name if response.prompt_feedback else "Unknown"
                    logger.error(f"Gemini generation blocked due to safety settings. Reason: {block_reason}")
                    safety_ratings_str = "\n".join(
                        [f"  - {rating.category.name}: {rating.probability.name}" for rating in
                         response.prompt_feedback.safety_ratings]) if response.prompt_feedback else "N/A"
                    return f"Error: Generation failed due to safety settings. Block Reason: {block_reason}\nSafety Ratings:\n{safety_ratings_str}"

                # Check finish reason in the first candidate
                first_candidate = response.candidates[0]
                finish_reason = first_candidate.finish_reason.name
                if finish_reason not in ["STOP", "MAX_TOKENS", "OTHER"]:  # Added OTHER as a possible valid finish reason
                    logger.warning(f"Gemini generation finished with reason: {finish_reason}. Check safety ratings.")
                    safety_ratings_str = "\n".join(
                        [f"  - {rating.category.name}: {rating.probability.name}" for rating in
                         first_candidate.safety_ratings]) if first_candidate.safety_ratings else "N/A"
                    if finish_reason == "SAFETY":
                        return f"Error: Generation stopped due to safety concerns. Finish Reason: {finish_reason}\nSafety Ratings:\n{safety_ratings_str}"
                    logger.warning(f"Finish Reason: {finish_reason}. Safety Ratings:\n{safety_ratings_str}")

                # Check if text is actually present in the response part
                generated_text = ""
                if first_candidate.content and first_candidate.content.parts:
                    generated_text = first_candidate.content.parts[0].text.strip()
                else:
                    logger.warning(f"Gemini response candidate has no text content. Finish Reason: {finish_reason}")
                    return f"Error: Gemini returned no text content. Finish Reason: {finish_reason}"

                logger.debug(f"--- Received response from Gemini ---")
                logger.debug(f"Response:\n{generated_text}")
                logger.debug(f"Finish Reason: {finish_reason}")
                logger.debug(f"--- End of Response ---")
                return generated_text

            except Exception as e:
                logger.error(f"An unexpected error occurred during Gemini API call: {e}", exc_info=True)
                raise  # Re-raise unexpected errors immediately

        logger.error("Failed to get response from Gemini after multiple retries.")
        return "Error: Could not get response from Google Gemini API."

    def get_model_name(self) -> str:
        """Returns the name of the model being used."""
        return self.model_name
