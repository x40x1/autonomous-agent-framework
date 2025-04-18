import yaml
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = 'config.yaml'

def load_config(config_path=DEFAULT_CONFIG_PATH):
    """Loads configuration from a YAML file."""
    try:
        # Load environment variables from .env file
        load_dotenv()

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Configuration loaded successfully from {config_path}")
            logger.debug(f"'enable_dangerous_tools' value from config: {config.get('enable_dangerous_tools')} (type: {type(config.get('enable_dangerous_tools'))})")

        # Override API key from environment variable if not set in config
        provider = config.get('llm_provider')

        if provider == 'openai' and config.get('openai', {}).get('api_key') is None:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                if 'openai' not in config:
                    config['openai'] = {}
                config['openai']['api_key'] = api_key
                logger.info("Loaded OpenAI API key from environment variable.")
            else:
                logger.warning("OpenAI API key not found in config file or environment variables.")
                # You might want to raise an error here depending on requirements
                # raise ValueError("OpenAI API key is required but not found.")

        elif provider == 'gemini' and config.get('gemini', {}).get('api_key') is None:
            api_key = os.getenv('GOOGLE_API_KEY')  # Use GOOGLE_API_KEY for Gemini
            if api_key:
                if 'gemini' not in config:
                    config['gemini'] = {}
                config['gemini']['api_key'] = api_key
                logger.info("Loaded Google API key from environment variable.")
            else:
                logger.warning("Google API key (GOOGLE_API_KEY) not found in config file or environment variables.")
                # You might want to raise an error here depending on requirements
                # raise ValueError("Google API key is required but not found.")

        if config.get('enable_dangerous_tools') == True:
             logger.warning("DANGEROUS TOOLS ARE ENABLED. The agent can execute arbitrary code and shell commands. PROCEED WITH EXTREME CAUTION.")

        return config
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file {config_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading config: {e}")
        raise

# Load config globally on import for easy access? Or pass it around?
# Passing it around is generally cleaner. Let's stick with that.

if __name__ == '__main__':
    # Example usage:
    try:
        # Assumes config.yaml and .env exist in the same directory for this test
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir) # Go up one level from utils
        test_config_path = os.path.join(project_root, 'config.yaml')
        test_env_path = os.path.join(project_root, '.env')

        if not os.path.exists(test_env_path):
            print(f"Warning: .env file not found at {test_env_path} for testing.")

        config = load_config(test_config_path)
        print("Config loaded:")
        print(config)

        # Test dangerous tools warning
        if config.get('enable_dangerous_tools'):
             print("\nWARNING: DANGEROUS TOOLS ARE ENABLED IN THE CONFIG.")

    except Exception as e:
        print(f"Failed to load config for testing: {e}")