Project Root: /Users/johngarfield/Documents/GitHub/codesum
Project Structure:
```
.
|-- .env.bak
|-- .gitignore
|-- LICENSE
|-- README.md
|-- env_example
|-- pyproject.toml
|-- requirements.txt
|-- src
    |-- codesum
        |-- __init__.py
        |-- app.py
        |-- config.py
        |-- file_utils.py
        |-- openai_utils.py
        |-- prompts
            |-- system_readme.md
            |-- system_summary.md
        |-- summary_utils.py
        |-- tui.py

```

---

## File: app.py

Error reading file: [Errno 2] No such file or directory: '/Users/johngarfield/Documents/GitHub/codesum/app.py'
---

## File: codesum.sh

Error reading file: [Errno 2] No such file or directory: '/Users/johngarfield/Documents/GitHub/codesum/codesum.sh'
---

## File: setup.py

Error reading file: [Errno 2] No such file or directory: '/Users/johngarfield/Documents/GitHub/codesum/setup.py'
---

## File: src/codesum/app.py

Summary:
```markdown
### Summary

The code is a Python script designed as an entry point for an application that generates code summaries optimized for large language models (LLMs), with an interactive text user interface (TUI). It uses the OpenAI API for AI-powered features. The script is structured to handle configuration, file selection, summary generation, and optional AI features like compressed summaries and README generation.

### Key Components

- **Argument Parsing**: Uses `argparse` to handle command-line arguments. The `--configure` flag triggers an interactive configuration wizard for setting up the API key and model.

- **Configuration Handling**: 
  - `config.configure_settings_interactive()`: Runs a wizard to configure settings.
  - `config.load_or_prompt_config()`: Loads configuration or prompts for missing API key.

- **OpenAI Client Initialization**: Attempts to initialize an OpenAI client using the provided API key. If unsuccessful, AI features are disabled.

- **File and Directory Management**:
  - `summary_utils.create_hidden_directory()`: Prepares the project directory structure.
  - `file_utils.parse_gitignore()`: Parses `.gitignore` to determine files to ignore.
  - `summary_utils.read_previous_selection()`: Loads previously selected files.
  - `tui.select_files()`: Runs an interactive file selection interface.

- **Summary Generation**:
  - `summary_utils.write_previous_selection()`: Saves the current file selection.
  - `summary_utils.create_code_summary()`: Generates a local code summary.
  - `summary_utils.copy_summary_to_clipboard()`: Copies the summary to the clipboard.

- **AI Features**:
  - Prompts the user to generate an AI-powered compressed summary using `summary_utils.create_compressed_summary()`.
  - Optionally generates or updates a `README.md` file using the compressed summary and OpenAI API via `openai_utils.generate_readme()`.

### Notes

- The script is designed to be run as a module (`python -m codesum.app`).
- It handles exceptions gracefully, providing feedback on errors and proceeding with limited functionality if necessary.
- The AI features are optional and depend on successful OpenAI client initialization.
- The script uses explicit relative imports for modules within the package.
```
---

## File: src/codesum/config.py

Summary:
```markdown
The code in `config.py` is part of a configuration management module for an application named "codesum". It handles loading, saving, and interacting with user configuration settings, specifically for managing an OpenAI API key and a language model (LLM) setting. The configuration is stored in a `.env` file located in the user's configuration directory.

### Key Components:

- **Constants:**
  - `APP_NAME`: The name of the application.
  - `CONFIG_DIR`: The directory where the configuration file is stored.
  - `CONFIG_FILE`: The path to the configuration file.
  - `DEFAULT_LLM_MODEL`: The default language model to use if none is specified.
  - `DEBUG_CONFIG`: A flag for enabling debug output.

- **Functions:**

  - `_debug_print(msg)`: Prints debug messages to stderr if `DEBUG_CONFIG` is `True`.

  - `ensure_config_paths()`: Ensures that the configuration directory and file exist, creating them if necessary.

  - `load_config() -> tuple[str | None, str]`: Loads the API key and LLM model from the configuration file. Returns a tuple of the API key and LLM model, using defaults if not set.

  - `save_config(api_key: str | None, llm_model: str)`: Saves the provided API key and LLM model to the configuration file and updates the environment variables for the current session.

  - `prompt_for_api_key_interactive() -> str | None`: Interactively prompts the user for an API key if it is not set. Returns the key or `None` if skipped.

  - `configure_settings_interactive()`: Provides an interactive wizard for the user to configure the API key and LLM model, allowing them to update or clear existing settings.

  - `load_or_prompt_config() -> tuple[str | None, str]`: Loads the configuration and prompts the user for an API key if it is missing. Returns the loaded or updated API key and LLM model.

### Notes:

- The module uses the `dotenv` library to manage environment variables stored in the `.env` file.
- Debugging is facilitated through conditional printing controlled by the `DEBUG_CONFIG` flag.
- The configuration is designed to be user-friendly, providing interactive prompts when necessary.
- The code ensures that environment variables are updated in the current session after any changes to the configuration file.
```
---
