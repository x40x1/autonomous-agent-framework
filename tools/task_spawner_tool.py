import logging
import multiprocessing
import uuid
import time
import traceback
from typing import List, Dict, Optional, Any

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# Global dictionary to store spawned process info (INSECURE - for demo only)
_background_tasks: Dict[str, Dict[str, Any]] = {}

def _agent_process_wrapper(task_id: str, goal: str, allowed_tools_config: List[str], result_queue: multiprocessing.Queue):
    """Target function for the spawned process with full agent setup."""
    import sys
    # Import required modules for agent setup within the process
    from utils.config import load_config
    from utils.logging_setup import setup_logging
    from llm_interface import get_llm_client
    from tools import get_available_tools
    from memory import SimpleMemory
    from agent import Agent

    # Setup logging for this process (could log to a task-specific file if desired)
    setup_logging(level=logging.DEBUG)
    local_logger = logging.getLogger(__name__)
    local_logger.info(f"[Task {task_id}] Process started for goal: {goal}")

    try:
        # Load configuration (adjust file path if needed)
        config = load_config("config.yaml")
        local_logger.debug(f"[Task {task_id}] Loaded configuration.")

        # Retrieve all available tools
        all_tools = get_available_tools(config)
        local_logger.debug(f"[Task {task_id}] Found tools: {[tool.name for tool in all_tools]}")

        # Filter tools if allowed_tools_config is provided
        if allowed_tools_config:
            filtered_tools = [tool for tool in all_tools if tool.name in allowed_tools_config]
            local_logger.info(f"[Task {task_id}] Filtered allowed tools: {[tool.name for tool in filtered_tools]}")
        else:
            filtered_tools = all_tools
            local_logger.info(f"[Task {task_id}] No allowed_tools filter provided; using all tools.")

        # Initialize the LLM client
        llm_client = get_llm_client(config)
        local_logger.debug(f"[Task {task_id}] LLM client initialized with model: {llm_client.get_model_name()}")

        # Initialize memory (each process uses its own instance)
        memory = SimpleMemory()
        local_logger.debug(f"[Task {task_id}] Memory initialized.")

        # Create an Agent instance
        max_iterations = config.get("max_iterations", 25)
        agent = Agent(llm=llm_client, tools=filtered_tools, memory=memory, max_iterations=max_iterations)
        local_logger.info(f"[Task {task_id}] Agent instance created. Starting agent run...")

        # Run the agent with the provided goal
        final_result = agent.run(goal)
        local_logger.info(f"[Task {task_id}] Agent run completed successfully.")

        # Put the successful result into the shared result queue
        result_queue.put({"task_id": task_id, "status": "completed", "result": final_result})

    except Exception as e:
        error_msg = f"Error during agent run: {e}\n{traceback.format_exc()}"
        local_logger.error(f"[Task {task_id}] {error_msg}")
        result_queue.put({"task_id": task_id, "status": "failed", "error": error_msg})


class TaskSpawnerTool(BaseTool):
    name = "task_spawner"
    description = (
        "Spawns a background task (potentially another agent instance) to work on a sub-goal. "
        "VERY EXPERIMENTAL AND COMPLEX. "
        "Input: {'action': 'spawn'|'check', 'params': {...}}. "
        "'spawn': {'sub_goal': '...', 'allowed_tools': ['tool_name', ... (optional)]} -> Returns task_id. "
        "'check': {'task_id': '...'} -> Returns task status ('running', 'completed', 'failed') and result/error. "
    )
    is_dangerous: bool = True

    def __init__(self):
        logger.info("TaskSpawnerTool initialized. VERY EXPERIMENTAL.")
        # Shared queue for results (Simplistic - real implementation needs better IPC)
        self.result_queue = multiprocessing.Queue()

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get('action')
        params = kwargs.get('params', {})
        if not action:
            return "Error: No action specified for task_spawner."
        action = action.lower()
        logger.info(f"Executing Task Spawner action: {action} with params: {params}")

        try:
            if action == 'spawn':
                sub_goal = params.get('sub_goal')
                allowed_tools = params.get('allowed_tools')  # Config for the sub-agent
                if not sub_goal:
                    return "Error: 'sub_goal' parameter missing for 'spawn'."

                task_id = f"task-{uuid.uuid4()}"

                process = multiprocessing.Process(
                    target=_agent_process_wrapper,
                    args=(task_id, sub_goal, allowed_tools, self.result_queue)
                )
                process.daemon = True  # Allow main process to exit even if children run
                process.start()

                _background_tasks[task_id] = {
                    "process": process,
                    "status": "running",
                    "result": None,
                    "error": None
                }
                logger.info(f"Spawned background task {task_id} for goal: '{sub_goal}'. Process ID: {process.pid}")
                return f"Successfully spawned background task. Task ID: {task_id}"

            elif action == 'check':
                task_id = params.get('task_id')
                if not task_id:
                    return "Error: 'task_id' parameter missing for 'check'."

                task_info = _background_tasks.get(task_id)
                if not task_info:
                    return f"Error: Task ID '{task_id}' not found."

                # Check the queue for updates (non-blocking)
                while not self.result_queue.empty():
                    try:
                        result_update = self.result_queue.get_nowait()
                        update_id = result_update.get("task_id")
                        if update_id in _background_tasks:
                            _background_tasks[update_id]["status"] = result_update.get("status", "unknown")
                            _background_tasks[update_id]["result"] = result_update.get("result")
                            _background_tasks[update_id]["error"] = result_update.get("error")
                            logger.info(f"Received update for task {update_id}: Status={_background_tasks[update_id]['status']}")
                    except multiprocessing.queues.Empty:
                        break  # No more updates for now

                # Check process status directly
                process: multiprocessing.Process = task_info["process"]
                if task_info["status"] == "running" and not process.is_alive():
                    # Process finished unexpectedly or crashed without sending to queue
                    task_info["status"] = "failed"
                    task_info["error"] = "Process terminated unexpectedly."
                    logger.warning(f"Task {task_id} process is not alive but status was 'running'. Marked as failed.")

                status = task_info["status"]
                result = task_info["result"]
                error = task_info["error"]

                output = f"Status of task '{task_id}': {status}\n"
                if status == "completed":
                    # Limit result length if needed
                    max_len = 1000
                    if result and len(str(result)) > max_len:
                        result = str(result)[:max_len] + "..."
                    output += f"Result: {result}"
                elif status == "failed":
                    output += f"Error: {error}"
                elif status == "running":
                    output += "Task is still running."

                return output.strip()

            else:
                return f"Error: Unknown task_spawner action '{action}'."

        except Exception as e:
            logger.error(f"An error occurred during Task Spawner action '{action}': {e}", exc_info=True)
            return f"Error during task_spawner action '{action}': {e}"