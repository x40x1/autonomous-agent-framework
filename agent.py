import logging
import time
from typing import List, Dict, Optional
from datetime import datetime  # Import datetime
from os import getcwd  # Add if missing
import json  # Added import

from llm_interface import BaseLLM
from tools import BaseTool, get_tool_descriptions, get_tool_names
from memory import SimpleMemory
from utils.parsing import parse_llm_response

logger = logging.getLogger(__name__)

class Agent:
    """The autonomous AI agent."""

    def __init__(self, llm: BaseLLM, tools: List[BaseTool], memory: SimpleMemory, max_iterations: int = 10, admin: bool = False):
        """
        Initializes the Agent.

        Args:
            llm: The language model interface.
            tools: A list of available tools.
            memory: The agent's memory module.
            max_iterations: Maximum number of thought-action cycles before stopping.
            admin: Flag indicating if the agent has admin privileges.
        """
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools} # Store tools in a dict for easy lookup
        self.memory = memory
        self.max_iterations = max_iterations
        self.admin = admin

        if self.admin:
            logger.info("Agent running with admin privileges.")
        else:
            logger.info("Agent running without admin privileges.")

        # Load the prompt template
        try:
            with open("prompts/react_agent_prompt.txt", "r") as f:
                self.prompt_template = f.read()
        except FileNotFoundError:
            logger.error("Prompt template file 'prompts/react_agent_prompt.txt' not found!")
            raise
        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            raise

        logger.info(f"Agent initialized with LLM: {llm.get_model_name()}, Tools: {list(self.tools.keys())}, Max Iterations: {max_iterations}")
        logger.debug(f"Enabled tools: {list(self.tools.keys())}")

    def _format_prompt(self, goal: str) -> str:
        """Formats the prompt with current goal, tools, history, and current time."""
        tool_descriptions = get_tool_descriptions(list(self.tools.values()))
        tool_names = get_tool_names(list(self.tools.values()))
        history = self.memory.get_history_string()
        # Get current date and time
        current_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Get current working directory
        current_dir = getcwd()

        prompt = self.prompt_template.format(
            goal=goal,
            tool_descriptions=tool_descriptions,
            tool_names=", ".join(tool_names),
            history=history,
            current_datetime=current_dt,
            current_directory=current_dir  # New placeholder for current directory
        )
        return prompt

    def _execute_tool(self, action_name: str, action_input: str) -> str:
        """Finds and executes the specified tool."""
        if action_name not in self.tools:
            logger.error(f"Action '{action_name}' requested but tool not found. Available tools: {list(self.tools.keys())}")
            return f"Error: Tool '{action_name}' not found. Available tools are: {', '.join(self.tools.keys())}"
        tool = self.tools[action_name]
        try:
            # If action_input is a JSON-like string, attempt to parse it into a dictionary.
            if isinstance(action_input, str) and action_input.strip().startswith("{"):
                try:
                    action_input_dict = json.loads(action_input)
                except json.decoder.JSONDecodeError as e:
                    logger.warning(f"Initial JSON parsing failed for input: {action_input}. Attempting fix. Error: {e}")
                    fixed_input = action_input.replace("'", "\"")
                    try:
                        action_input_dict = json.loads(fixed_input)
                    except json.decoder.JSONDecodeError as e2:
                        logger.error(f"Failed to parse action input even after fix: {fixed_input}. Error: {e2}", exc_info=True)
                        return f"Error: Failed to parse JSON input. Please provide a valid JSON dictionary. Error: {e2}"
                    else:
                        action_input = action_input_dict
                else:
                    action_input = action_input_dict
            # Unpack arguments if action_input is a dict; otherwise, pass the raw input.
            observation = tool.execute(**action_input) if isinstance(action_input, dict) else tool.execute(action_input)
            logger.info(f"Executing tool '{action_name}' with input: '{str(action_input)[:100]}{'...' if len(str(action_input))>100 else ''}'")
            logger.info(f"Tool '{action_name}' executed. Observation: {str(observation)[:100]}{'...' if len(str(observation))>100 else ''}")
            return str(observation)
        except TypeError as te:
            logger.error(f"TypeError executing tool '{action_name}' with input '{action_input}'. Does the tool expect different arguments? Error: {te}", exc_info=True)
            return f"Error: Tool '{action_name}' failed due to incorrect input arguments. Check tool description and input format. Error: {te}"
        except Exception as e:
            logger.error(f"Error executing tool '{action_name}' with input '{action_input}': {e}", exc_info=True)
            return f"Error: An unexpected error occurred while executing tool '{action_name}': {e}"

    def run(self, goal: str) -> str:
        """
        Runs the agent to achieve the given goal.

        Args:
            goal: The objective for the agent.

        Returns:
            The final result or status message.
        """
        logger.info(f"--- Starting Agent Run ---")
        logger.info(f"Goal: {goal}")
        self.memory.clear()
        start_time = time.time()

        for i in range(self.max_iterations):
            logger.info(f"--- Iteration {i + 1}/{self.max_iterations} ---")

            # 1. Format Prompt
            current_prompt = self._format_prompt(goal)
            # logger.debug(f"Formatted Prompt:\n{current_prompt}") # Can be very long

            # 2. Generate Response (Thought, Action, Action Input)
            try:
                llm_response_text = self.llm.generate(current_prompt)
                if not llm_response_text or llm_response_text.startswith("Error:"):
                     logger.error(f"LLM failed to generate a valid response. Response: {llm_response_text}")
                     return f"Agent stopped: LLM failed to generate response. Last error: {llm_response_text}"
            except Exception as e:
                logger.error(f"LLM generation failed with exception: {e}", exc_info=True)
                return f"Agent stopped: LLM generation encountered an error: {e}"


            # 3. Parse Response
            parsed_response = parse_llm_response(llm_response_text)
            thought = parsed_response["thought"]
            action_name = parsed_response["action"]
            action_input = parsed_response["action_input"]
            final_answer = parsed_response["final_answer"]

            logger.info(f"Agent Thought: {thought}")

            # 4. Check for Final Answer
            if final_answer is not None:
                logger.info(f"Agent provided Final Answer: {final_answer}")
                end_time = time.time()
                logger.info(f"--- Agent Run Finished (Goal Achieved) ---")
                logger.info(f"Total time: {end_time - start_time:.2f} seconds")
                logger.info(f"Total iterations: {i + 1}")
                return f"Goal Achieved: {final_answer}"

            # 5. Validate Action
            if not action_name:
                 logger.warning("LLM did not provide an action or final answer in this iteration. Asking LLM to try again or clarify.")
                 # We need an observation to continue the loop. Provide feedback.
                 observation = "Observation: No action was specified. Please provide an action or a final answer."
                 # We still need to record this 'non-action' step in memory
                 self.memory.add_interaction(thought, "No Action", "", observation)
                 continue # Go to next iteration

            if action_name not in self.tools:
                 logger.error(f"LLM requested invalid action: '{action_name}'. Available tools: {list(self.tools.keys())}")
                 observation = f"Observation: Error - Tool '{action_name}' is not available. Please choose from: {', '.join(self.tools.keys())}."
                 self.memory.add_interaction(thought, action_name, action_input, observation)
                 continue # Go to next iteration

            # 6. Execute Action
            logger.info(f"Agent Action: {action_name}")
            logger.info(f"Agent Action Input: {action_input}")
            observation = self._execute_tool(action_name, action_input)


            # 7. Add to Memory
            self.memory.add_interaction(thought, action_name, action_input, observation)
            # logger.debug(f"Current Memory:\n{self.memory.get_history_string()}") # Can be very verbose

            # Optional: Add a small delay to avoid overwhelming APIs or getting rate limited
            # time.sleep(1)

        # Loop finished without Final Answer
        logger.warning(f"Agent stopped: Reached maximum iterations ({self.max_iterations}) without achieving the goal.")
        end_time = time.time()
        logger.info(f"--- Agent Run Finished (Max Iterations Reached) ---")
        logger.info(f"Total time: {end_time - start_time:.2f} seconds")
        return f"Agent stopped: Reached maximum iterations ({self.max_iterations}). The goal may not be fully achieved. Check logs and memory."