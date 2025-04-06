import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# Define the structure of a memory item
MemoryItem = Tuple[str, str, str, str] # (Thought, Action, Action Input, Observation)

class SimpleMemory:
    """A simple chronological memory for the agent."""

    def __init__(self, max_context_tokens: Optional[int] = None):
        """
        Initializes the memory.
        Args:
            max_context_tokens: Optional limit for total tokens (rough estimate based on chars).
                                If None, no limit is applied (can lead to large prompts).
        """
        self.history: List[MemoryItem] = []
        # TODO: Implement token counting / limiting if max_context_tokens is set
        # This requires a tokenizer (like tiktoken for OpenAI) and is more complex.
        # For now, we'll rely on the LLM's context window and max_iterations.
        if max_context_tokens:
            logger.warning("max_context_tokens is not fully implemented in SimpleMemory yet. Memory might exceed limits.")


    def add_interaction(self, thought: str, action: str, action_input: str, observation: str):
        """Adds a complete thought-action-observation cycle to the memory."""
        if not isinstance(thought, str): thought = str(thought)
        if not isinstance(action, str): action = str(action)
        if not isinstance(action_input, str): action_input = str(action_input)
        if not isinstance(observation, str): observation = str(observation)

        self.history.append((thought, action, action_input, observation))
        logger.debug(f"Added to memory: T={thought[:50]}..., A={action}, I={action_input[:50]}..., O={observation[:50]}...")

    def get_history_string(self) -> str:
        """Formats the entire history into a string suitable for the LLM prompt."""
        if not self.history:
            return "No history yet."

        formatted_history = ""
        for thought, action, action_input, observation in self.history:
            formatted_history += f"Thought: {thought}\n"
            formatted_history += f"Action: {action}\n"
            formatted_history += f"Action Input: {action_input}\n"
            formatted_history += f"Observation: {observation}\n\n" # Add newline between steps

        return formatted_history.strip() # Remove trailing newline


    def clear(self):
        """Clears the memory."""
        self.history = []
        logger.info("Memory cleared.")