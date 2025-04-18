# Autonomous AI Agent Framework

**🛑 EXTREME WARNING: HIGH CAPABILITY & SIGNIFICANT RISK 🛑**

This framework is an **experimental project** designed for maximum agent capability. It intentionally includes tools that grant potentially **unrestricted access** to your system and data.

**⚠️ USE ENTIRELY AT YOUR OWN RISK. YOU ARE SOLELY RESPONSIBLE FOR ANY DAMAGE OR CONSEQUENCES. ⚠️**

---

## Project Status: Experimental & In Development

*   **This is NOT a finished product.** It is an ongoing experiment and development effort.
*   **Expect Bugs:** You may encounter bugs, unexpected behavior, or incomplete features.
*   **Contributions Welcome:** Please see the [Contributing](#contributing) section if you'd like to help improve the framework.

---

## Overview

This framework provides a foundation for building autonomous AI agents that can pursue goals using a variety of tools. It leverages Large Language Models (LLMs) and a ReAct (Reason-Act-Observe) loop to interact with its environment.

**Key Risks:**

*   **Data Loss/Corruption:** The agent can modify or delete files (`file_system`, `code_modifier`).
*   **Security Breach:** Arbitrary command execution (`command_line`), code execution (`python_exec`), and web interaction (`browser_automation`) can lead to malware, data exposure, or system compromise.
*   **Financial Loss:** Interactions with APIs or websites could incur costs or perform unwanted financial actions.
*   **Unintended Actions:** Misinterpretations can lead to harmful emails, messages, or online actions.
*   **Resource Abuse:** High consumption of system resources or API credits.
*   **Instability:** Self-modification (`code_modifier`) or task spawning (`task_spawner`) can cause crashes.

**Safety Recommendations:**

*   **Isolation is CRITICAL:** Run **ONLY** in isolated, disposable environments (VMs, containers) with **NO** access to sensitive data or systems.
*   **Network Restrictions:** Limit network access where possible.
*   **Least Privilege:** Use dedicated API keys/credentials with minimal permissions. **NEVER** use root/admin accounts.
*   **Monitor Closely:** Observe agent actions and logs in real-time. Be ready to terminate immediately.
*   **Review Configuration:** Carefully check `config.yaml`, especially `enable_dangerous_tools`.
*   **Understand the Tools:** Know what capabilities you are enabling.

## Features

*   **Goal-Oriented:** Attempts to achieve user-defined goals.
*   **LLM Agnostic:** Supports OpenAI, Google Gemini, and local models via Ollama.
*   **Extensive Toolset:**
    *   Standard: `web_search`, `open_url`, `ask_human`, `read_screen`
    *   Dangerous (require `enable_dangerous_tools: true`): `file_system`, `command_line`, `python_exec`, `database`, `code_modifier`, `task_spawner` (Experimental)
    *   Other: `browser_automation` (Use with caution)
*   **Plugin System:** Extend capabilities with custom or community plugins.
*   **ReAct Framework:** Uses a Reason-Act-Observe loop for planning and execution.
*   **Basic Memory:** Simple chronological memory.
*   **Configurable:** Settings managed via `config.yaml`.

## Setup

1.  **Prerequisites:**
    *   Python 3.8+
    *   Git (for cloning and plugin management)
    *   Access to an LLM (OpenAI/Google API Key or a running Ollama instance)
    *   **(Optional) Browser Automation:** Requires Playwright (`playwright install`).
    *   **(Optional) Screen Reading:** Requires Tesseract OCR engine installed and in PATH (or path specified in `config.yaml`). See [Tesseract Installation](https://github.com/tesseract-ocr/tesseract#installing-tesseract).

2.  **Clone the Repository:**
    ```bash
    # git clone https://github.com/x40x1/autonomous-agent-framework.git
    # cd autonomous-agent-framework
    ```

3.  **Create Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Windows: .\venv\Scripts\activate
    # macOS/Linux: source venv/bin/activate
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    # Install optional dependencies if needed:
    # playwright install # For browser_automation tool
    ```

5.  **Configure (`config.yaml`):**
    *   Copy/rename `config.example.yaml` to `config.yaml`.
    *   Set `llm_provider` (`openai`, `gemini`, or `ollama`).
    *   Configure the chosen LLM provider section (model name, etc.).
    *   **API Keys:**
        *   **Recommended:** Create a `.env` file in the project root:
            ```dotenv
            # .env
            OPENAI_API_KEY="sk-..."
            GOOGLE_API_KEY="..."
            ```
        *   *Alternatively (less secure):* Set keys directly in `config.yaml`.
    *   **⚠️ DANGEROUS TOOLS:**
        *   Review the `enable_dangerous_tools` setting.
        *   **Defaults to `false` (safer).**
        *   Set to `true` **ONLY** if you fully understand and accept the extreme risks involved. Tools marked `is_dangerous = True` in their code will only load if this is `true`.
    *   **Tool Settings:** Review the `tools:` section for specific tool configurations (database connections, workspace paths, etc.).

6.  **Tool-Specific Setup:**
    *   Ensure prerequisites (like Tesseract or Playwright) for the tools you intend to use are met.

## Usage (Command Line)

Run the agent from the project's root directory:

```bash
python main.py "Your goal for the agent here" [--config path/to/your_config.yaml] [--verbose]
```

*   `"Your goal..."`: The objective for the agent.
*   `--config`: (Optional) Specify a different configuration file. Defaults to `config.yaml`.
*   `--verbose`: (Optional) Enable more detailed logging output (DEBUG level).

*Note: The `--enable-dangerous-tools` command-line flag is deprecated. Control dangerous tools via the `enable_dangerous_tools` setting in `config.yaml`.*

## Streamlit UI Usage

Interact with the agent through a web interface.

1.  **Install Streamlit:**
    ```bash
    pip install streamlit
    ```

2.  **Run the Streamlit App:**
    From the project root directory:
    ```bash
    streamlit run streamlit_app.py
    ```

3.  **Access the UI:**
    Open the URL shown in your terminal (usually `http://localhost:8501`).

4.  **Using the UI:**
    *   Enter your goal in the chat input box.
    *   The agent's execution trace (Thought, Action, Observation steps) will be displayed.
    *   Use the sidebar to view the configuration and clear the agent's memory/chat history.

## Plugin System

Extend the agent's capabilities by adding new tools via plugins.

**1. Installing Plugins:**

Use the `manage_plugins.py` script to install plugins from Git repositories into the `plugins/` directory.

```bash
# Install from URL (uses repo name as directory name)
python manage_plugins.py install https://github.com/someuser/agent-plugin-example.git

# Install from URL with a custom directory name
python manage_plugins.py install https://github.com/anotheruser/complex_tool.git --name my_complex_tool
```

**2. Listing Installed Plugins:**

```bash
python manage_plugins.py list
```

**3. Enabling Plugins:**

Add the plugin's directory name (e.g., `agent-plugin-example`, `my_complex_tool`) to the `plugins.enabled` list in `config.yaml`:

```yaml
# config.yaml
# ...
plugins:
  enabled:
    - agent-plugin-example
    - my_complex_tool
    # - other_plugin_directory_name
# ...
```
The agent will attempt to load tools from enabled plugins on startup.

**4. Creating Plugins:**

*   **Structure:** Create a directory (e.g., `my_plugin`). Inside, create Python files defining your tool classes.
*   **Tool Class:** Inherit from `tools.base_tool.BaseTool`. Define `name` and `description`. Implement the `execute` method.
    ```python
    # plugins/my_plugin/my_tool_file.py
    from tools.base_tool import BaseTool
    import logging

    logger = logging.getLogger(__name__)

    class MyCustomTool(BaseTool):
        name = "my_custom_tool"
        description = "Does something cool. Input: {'param': 'value'}"
        # Optional: Mark as dangerous if it performs risky operations
        # is_dangerous = True # Defaults to False if not present

        def __init__(self, config_param=None): # Optional: Accept config
            logger.info(f"MyCustomTool initialized with config: config_param")
            # ... init logic ...

        def execute(self, **kwargs) -> str:
            param = kwargs.get('param')
            logger.info(f"Executing MyCustomTool with param: param")
            # ... execution logic ...
            return "Result of my custom tool"
    ```
*   **Dependencies:** Include a `requirements.txt` in your plugin directory if it has specific dependencies. Users must install these manually (`pip install -r plugins/my_plugin/requirements.txt`).
*   **Configuration:** Plugin tools can receive configuration from `config.yaml` under `plugins.config.<plugin_name>.<tool_name>`. The tool's `__init__` method needs to be adapted to accept these parameters if needed (the basic loader currently doesn't pass config automatically, requiring refinement).
*   **Publishing:** Share your plugin by publishing its directory as a Git repository.

**Plugin Security:** Install plugins only from trusted sources. They execute arbitrary code and can be dangerous, especially if `enable_dangerous_tools` is `true`.

## Contributing

This project is experimental and contributions are welcome! If you find bugs, have feature ideas, or want to improve the code, please check for a `CONTRIBUTING.md` file and follow standard GitHub practices (Issues, Pull Requests). Be mindful of the project's experimental nature when contributing.
