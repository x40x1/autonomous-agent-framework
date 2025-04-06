import argparse
import logging
import os
import sys
from pathlib import Path

try:
    import git
except ImportError:
    print("Error: GitPython is not installed. Please install it: pip install GitPython")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Assume the script is run from the project root
PROJECT_ROOT = Path(__file__).parent.resolve()
PLUGINS_DIR = PROJECT_ROOT / "plugins"

def install_plugin(repo_url: str, plugin_name: str = None):
    """Clones a plugin repository into the plugins directory."""
    if not repo_url:
        logger.error("Repository URL cannot be empty.")
        return

    if not plugin_name:
        # Try to infer name from URL (e.g., https://github.com/user/my-plugin.git -> my-plugin)
        try:
            plugin_name = Path(repo_url).stem
            if not plugin_name:
                raise ValueError("Could not infer plugin name.")
        except Exception:
            logger.error("Could not automatically determine plugin name from URL. Please provide it using --name.")
            return

    target_dir = PLUGINS_DIR / plugin_name
    logger.info(f"Attempting to install plugin '{plugin_name}' from {repo_url} into {target_dir}")

    if target_dir.exists():
        logger.warning(f"Plugin directory '{target_dir}' already exists. Skipping installation.")
        # TODO: Add an --update flag to pull changes?
        return

    try:
        PLUGINS_DIR.mkdir(exist_ok=True) # Ensure plugins directory exists
        git.Repo.clone_from(repo_url, target_dir)
        logger.info(f"Successfully installed plugin '{plugin_name}'.")
        logger.info(f"To enable it, add '{plugin_name}' to the 'plugins.enabled' list in your config.yaml.")
    except git.GitCommandError as e:
        logger.error(f"Git command failed: {e}")
    except Exception as e:
        logger.error(f"Failed to install plugin '{plugin_name}': {e}", exc_info=True)

def list_plugins():
    """Lists installed plugins."""
    if not PLUGINS_DIR.is_dir():
        print("Plugins directory does not exist. No plugins installed.")
        return

    print("Installed plugins:")
    found = False
    for item in PLUGINS_DIR.iterdir():
        if item.is_dir() and (item / '.git').is_dir(): # Basic check for a git repo
            print(f"- {item.name}")
            found = True
    if not found:
        print("(No valid plugin directories found)")


def main():
    parser = argparse.ArgumentParser(description="Manage Agent Framework Plugins")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Install command
    parser_install = subparsers.add_parser('install', help='Install a plugin from a Git repository')
    parser_install.add_argument('repo_url', help='URL of the Git repository for the plugin')
    parser_install.add_argument('-n', '--name', help='Optional name for the plugin directory (derived from URL if omitted)')

    # List command
    parser_list = subparsers.add_parser('list', help='List installed plugins')

    # TODO: Add uninstall, update commands

    args = parser.parse_args()

    if args.command == 'install':
        install_plugin(args.repo_url, args.name)
    elif args.command == 'list':
        list_plugins()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
