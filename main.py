import argparse
import logging
import sys
import ctypes

from utils.config import load_config
from utils.logging_setup import setup_logging
from llm_interface import get_llm_client
from tools import get_available_tools
from memory import SimpleMemory
from agent import Agent

# Setup basic logging before config is loaded for early messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Agent Framework")
    parser.add_argument("goal", help="The main goal for the AI agent to achieve.")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to the configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG level) logging."
    )
    parser.add_argument(
        "--enable-dangerous-tools",
        action="store_true",
        help="Explicitly override config and enable dangerous tools (command_line, python_exec). USE WITH EXTREME CAUTION."
    )

    args = parser.parse_args()

    # --- Configuration and Logging ---
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.critical(f"Failed to load configuration: {e}", exc_info=True)
        sys.exit(1)

    is_admin = False # Default to not admin
    # If admin privileges are required by config, check and elevate if necessary.
    if config.get('admin_privileges', False):
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            logger.info("Admin privileges required. Relaunching with elevated rights...")
            params = " ".join(sys.argv)
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            sys.exit(0)
        else:
            logger.info("Process running with admin privileges.")

    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level) # Reconfigure logging with desired level

    # Override dangerous tools setting if command-line flag is set
    if args.enable_dangerous_tools:
         if not config.get('enable_dangerous_tools', False):
              logger.critical("OVERRIDING CONFIG: Enabling dangerous tools via command-line flag!")
              config['enable_dangerous_tools'] = True
         else:
              logger.warning("Command-line flag --enable-dangerous-tools used, but already enabled in config.")

    # --- Setup Components ---
    try:
        # LLM Client
        llm_client = get_llm_client(config)

        # Tools (Tools will check config for dangerous tools internally now)
        available_tools = get_available_tools(config)
        if not available_tools:
             logger.warning("No tools were initialized. The agent may have limited capabilities.")


        # Memory
        memory = SimpleMemory() # Add config options later if needed

        # Agent
        max_iterations = config.get('max_iterations', 15)
        agent = Agent(
            memory=memory,
            max_iterations=max_iterations,
            admin=is_admin
        )

    except ValueError as e:
         logger.critical(f"Configuration error during setup: {e}", exc_info=True)
         sys.exit(1)
    except ConnectionError as e: # Catch connection errors from LLM/Ollama init
         logger.critical(f"Connection error during setup: {e}", exc_info=True)
         sys.exit(1)
    except Exception as e:
        logger.critical(f"Unexpected error during agent initialization: {e}", exc_info=True)
        sys.exit(1)

    # --- Run Agent ---
    try:
        final_result = agent.run(args.goal)
        print("\n" + "="*30 + " Agent Run Complete " + "="*30)
        print(f"Final Result:\n{final_result}")
        print("="*80)
    except KeyboardInterrupt:
        logger.warning("Agent run interrupted by user (Ctrl+C).")
        print("\nAgent run interrupted.")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred during agent execution: {e}", exc_info=True)
        print(f"\nAn critical error occurred: {e}. Check logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()