import asyncio  # new import
try:
    asyncio.get_running_loop()
except RuntimeError:
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)

# Add torch import handling
import sys
from unittest.mock import MagicMock
try:
    # Try importing torch to check if it works correctly
    import torch
except (RuntimeError, ImportError) as e:
    # If torch import fails, mock the module to prevent errors
    sys.modules['torch'] = MagicMock()
    sys.modules['torch._classes'] = MagicMock()
    sys.modules['torch._C'] = MagicMock()
    print("Warning: torch module mocked due to import error")

import streamlit as st
import logging
import time
from utils.config import load_config
from utils.logging_setup import setup_logging
from llm_interface import get_llm_client
from tools import get_available_tools
from memory import SimpleMemory, MemoryItem
from agent import Agent

# --- Configuration and Setup ---
# Configure logging (console output will still appear)
# Setup logging only once - but use DEBUG level to see all messages
if 'logging_configured' not in st.session_state:
    setup_logging(level=logging.DEBUG)  # Changed to DEBUG level for more verbose output
    st.session_state.logging_configured = True

logger = logging.getLogger(__name__)
logger.debug("Streamlit app starting with DEBUG logging enabled")

# Load config only once
if 'config' not in st.session_state:
    try:
        st.session_state.config = load_config("config.yaml")
        # Force explicit log message about the dangerous tools status
        dangerous_enabled = st.session_state.config.get('enable_dangerous_tools', False)
        logger.warning(f"DIRECT CONFIG CHECK: enable_dangerous_tools = {dangerous_enabled} ({type(dangerous_enabled)})")
    except Exception as e:
        st.error(f"Failed to load configuration: {e}")
        st.stop()

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize agent memory in session state if it doesn't exist
if "agent_memory" not in st.session_state:
    st.session_state.agent_memory = SimpleMemory()
    logger.info("Initialized new agent memory in session state.")

# --- UI Components ---
st.title("Autonomous Assistant Chat UI")
st.markdown("Enter your goal below and the system will attempt to achieve it. Conversation history is preserved.")  # Updated description

# Sidebar for configuration and controls
with st.sidebar:
    st.header("Agent Controls")
    if st.button("Clear Agent Memory & Chat History"):
        st.session_state.agent_memory.clear()
        st.session_state.messages = []
        logger.info("Agent memory and chat history cleared by user.")
        st.rerun() # Rerun to reflect the cleared state

    st.header("Configuration")
    st.json(st.session_state.config, expanded=False)
    
    # Add explicit status indicator for dangerous tools
    dangerous_enabled = st.session_state.config.get('enable_dangerous_tools', False)
    if dangerous_enabled:
        st.warning("⚠️ DANGEROUS TOOLS ARE ENABLED! Command line and Python execution are available.")
    else:
        st.info("🛡️ Dangerous tools are disabled (safe mode).")


# Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # Handle different message types (simple text, agent steps)
        if isinstance(message["content"], str):
            st.markdown(message["content"])
        # Check if it's a list containing tuples of length 4 (representing MemoryItem)
        elif isinstance(message["content"], list) and all(isinstance(item, tuple) and len(item) == 4 for item in message["content"]):
             st.markdown("Agent execution trace:")
             for i, (thought, action, action_input, observation) in enumerate(message["content"], start=1):
                 with st.expander(f"Step {i}: Action '{action}'"):
                     st.markdown(f"**Thought:**\n```\n{thought}\n```")
                     st.markdown(f"**Action:** `{action}`")
                     st.markdown(f"**Action Input:**\n```\n{action_input}\n```")
                     st.markdown(f"**Observation:**\n```\n{observation}\n```")


# Get user input using chat_input
if goal := st.chat_input("Enter your goal for the agent:"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": goal})
    with st.chat_message("user"):
        st.markdown(goal)

    # Prepare and run the agent
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        status_placeholder.status("Running agent...", expanded=True)

        try:
            # Instantiate components using loaded config and session memory
            config = st.session_state.config
            llm_client = get_llm_client(config)
            
            # Get available tools and immediately check if dangerous tools are included
            available_tools = get_available_tools(config)
            tool_names = [tool.name for tool in available_tools]
            logger.info(f"Enabled tools: {tool_names}")  # <-- New logger line
            has_dangerous = any(name in ['command_line', 'python_exec'] for name in tool_names)
            
            # Display the tools loaded for this run with emphasis on dangerous tools
            if has_dangerous:
                dangerous_names = [name for name in tool_names if name in ['command_line', 'python_exec']]
                safe_names = [name for name in tool_names if name not in ['command_line', 'python_exec']]
                st.warning(f"⚠️ DANGEROUS TOOLS ACTIVE: `{', '.join(dangerous_names)}`")
                st.info(f"Standard tools: `{', '.join(safe_names)}`")
            else:
                st.info(f"Agent initialized with tools: `{', '.join(tool_names)}`")
                
            memory = st.session_state.agent_memory # Use memory from session state
            max_iterations = config.get("max_iterations", 25)

            # Create a *new* agent instance for each run, but pass the *persistent* memory
            agent = Agent(llm=llm_client, tools=available_tools, memory=memory, max_iterations=max_iterations)

            # Run the agent (this blocks until completion in this simplified version)
            start_run_time = time.time()
            final_result = agent.run(goal)
            end_run_time = time.time()

            status_placeholder.success(f"Agent run completed in {end_run_time - start_run_time:.2f} seconds.")

            # Display final result
            st.markdown("### Final Result")  # Renamed to avoid AI-specific phrasing
            st.markdown(final_result)

            # Add final result and execution trace to chat history
            # Store the history *from this specific run* for display
            current_run_history = memory.history[:] # Make a copy
            st.session_state.messages.append({"role": "assistant", "content": final_result})
            if current_run_history:
                 st.session_state.messages.append({"role": "assistant", "content": current_run_history})
                 st.markdown("---")
                 st.markdown("### Execution Trace (This Run)")  # Updated heading
                 for i, (thought, action, action_input, observation) in enumerate(current_run_history, start=1):
                     with st.expander(f"Step {i}: Action '{action}'"):
                         st.markdown(f"**Thought:**\n```\n{thought}\n```")
                         st.markdown(f"**Action:** `{action}`")
                         st.markdown(f"**Action Input:**\n```\n{action_input}\n```")
                         st.markdown(f"**Observation:**\n```\n{observation}\n```")


        except Exception as e:
            logger.error(f"An error occurred during run: {e}", exc_info=True)  # Revised log message
            status_placeholder.error(f"Run failed: {e}")  # Revised error text
            st.session_state.messages.append({"role": "assistant", "content": f"Error during execution: {e}"})

        # Note: In this version, the agent memory (st.session_state.agent_memory)
        # persists across runs unless cleared. The history displayed is appended
        # to the overall chat log.