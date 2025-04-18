from abc import ABC, abstractmethod
from typing import Any

class BaseTool(ABC):
    """Abstract base class for all tools."""

    # These should be defined in subclasses
    name: str = "base_tool"
    description: str = "This is a placeholder description for the base tool."

    @abstractmethod
    def execute(self, *args, **kwargs) -> str:
        """
        Executes the tool's functionality.

        Args:
            *args: Positional arguments for the tool.
            **kwargs: Keyword arguments for the tool.
                      Often, a single string 'input_str' or similar is expected based on parsing.

        Returns:
            A string representing the result or observation from the tool's execution.
            Should include error messages if execution fails.
        """
        pass

    def get_description(self) -> str:
        """Returns the tool's description."""
        # Future: Could potentially generate more dynamic descriptions if needed
        return f"{self.name}: {self.description}"