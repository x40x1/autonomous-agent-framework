import logging
from typing import Dict, Any

from .base_llm import BaseLLM
from .openai_llm import OpenAILLM
from .ollama_llm import OllamaLLM
from .gemini_llm import GeminiLLM  # Already updated

logger = logging.getLogger(__name__)

def get_llm_client(config: Dict[str, Any]) -> BaseLLM:
    """
    Factory function to get the appropriate LLM client based on configuration.
    """
    provider = config.get('llm_provider')
    if not provider:
        raise ValueError("LLM provider ('llm_provider') is not specified in configuration.")

    logger.info(f"Selected LLM Provider: {provider}")

    if provider == 'openai':
        if 'openai' not in config:
            raise ValueError("OpenAI configuration ('openai') missing in config file.")
        return OpenAILLM(config)
    elif provider == 'ollama':
        if 'ollama' not in config:
            raise ValueError("Ollama configuration ('ollama') missing in config file.")
        try:
            return OllamaLLM(config)
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.error(f"Failed to initialize Ollama LLM: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing Ollama LLM: {e}", exc_info=True)
            raise
    elif provider == 'gemini':  # Gemini provider
        if 'gemini' not in config:
            raise ValueError("Gemini configuration ('gemini') missing in config file.")
        try:
            return GeminiLLM(config)
        except (ConnectionError, ValueError) as e:
            logger.error(f"Failed to initialize Gemini LLM: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing Gemini LLM: {e}", exc_info=True)
            raise
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")