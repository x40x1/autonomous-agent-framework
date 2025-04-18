from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseLLM(ABC):
    """Abstract base class for Language Model interfaces."""

    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """Initializes the LLM interface with specific configurations."""
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, stop: list[str] = None) -> str:
        """
        Generates text based on the provided prompt.

        Args:
            prompt: The input text prompt for the LLM.
            stop: A list of sequences to stop generation at.

        Returns:
            The generated text response from the LLM.
        """
        pass

    def get_model_name(self) -> str:
        """Returns the name of the model being used."""
        return self.config.get('model', 'unknown')