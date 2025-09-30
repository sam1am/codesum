Project Root: /Users/johngarfield/Documents/GitHub/codesum
Project Structure:
```
.
|-- .claude
    |-- settings.local.json
|-- .gitignore
|-- LICENSE
|-- MCP_USAGE.md
|-- README.md
|-- example_mcp_client.py
|-- pyproject.toml
|-- release.sh
|-- src
    |-- codesum
        |-- __init__.py
        |-- app.py
        |-- config.py
        |-- file_utils.py
        |-- folder_utils.py
        |-- mcp_http_server.py
        |-- mcp_server.py
        |-- openai_utils.py
        |-- prompts
            |-- system_readme.md
            |-- system_summary.md
        |-- summary_utils.py
        |-- tui.py
|-- test_mcp_server.py

```

---
## File: src/codesum/app.py [AI Compressed]

The `app.py` script is the main entry point for a code summarization application optimized for use with Large Language Models (LLMs). It provides both an interactive Text User Interface (TUI) and a server mode for generating code summaries. Below is a detailed breakdown of its components:

### Main Function
- **Purpose**: Acts as the primary entry point for the application, handling argument parsing, configuration, and execution of the main functionalities.
- **Argument Parsing**: Utilizes `argparse` to handle command-line arguments:
  - `--configure`: Launches an interactive configuration wizard for setting up the API key and model, then exits.
  - `--mcp-server`: Runs the MCP server instead of the interactive application.
  - `--mcp-host` and `--mcp-port`: Specify the host and port for the MCP server.
- **Configuration Mode**: If `--configure` is set, it runs a configuration wizard and exits.
- **MCP Server Mode**: If `--mcp-server` is set, it starts the MCP server with specified host and port.
- **Normal Operation**:
  - Sets the current working directory as the base directory.
  - Loads configuration settings for the API key and LLM model.
  - Prepares the project directory structure and handles `.gitignore` and custom ignore files.
  - Loads any previous file selections.
  - Runs an interactive file selection interface.
  - Saves the current selection of files.
  - Generates a local code summary, initializing an OpenAI client if compressed summaries are needed.
  - Counts tokens in the generated summary.
  - Copies the summary to the clipboard.
  - Displays a summary of the operation, including selected files and token count, in an ASCII art format.

### Key Components
- **Configuration Handling**: Uses the `config` module to load and save API keys and model configurations.
- **File Utilities**: Utilizes `file_utils` to parse `.gitignore` files and manage default and custom ignore lists.
- **Summary Utilities**: Uses `summary_utils` for creating directories, reading/writing selections, and generating summaries.
- **TUI**: The `tui` module provides an interactive interface for file selection.
- **OpenAI Client**: The `openai_utils` module is used for token counting and potentially interacting with OpenAI's API for compressed summaries.

### Notes
- The script is designed to be run as a standalone application (`python -m codesum.app`).
- It handles errors gracefully, particularly when dealing with file operations and OpenAI client initialization.
- ASCII art is used for a visually appealing summary of the operation's results.

This script is a comprehensive tool for generating code summaries with options for interactive configuration and server-based operation, making it versatile for different use cases.

---
## File: src/codesum/config.py

```py
# src/codesum/config.py

import os
from pathlib import Path
import platformdirs
from dotenv import load_dotenv, set_key, find_dotenv, unset_key
import sys

APP_NAME = "codesum"
CONFIG_DIR = Path(platformdirs.user_config_dir(APP_NAME))
CONFIG_FILE = CONFIG_DIR / "settings.env"

DEFAULT_LLM_MODEL = "gpt-4o" # Keep a default

# Simple flag for verbose debugging output
DEBUG_CONFIG = False # Set to True locally if you need deep tracing

def _debug_print(msg):
    """Helper for conditional debug printing."""
    if DEBUG_CONFIG:
        print(f"[Config Debug] {msg}", file=sys.stderr) # Print to stderr

def ensure_config_paths():
    """Ensures the configuration directory and file exist."""
    _debug_print(f"Ensuring config path: {CONFIG_FILE}")
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.is_file():
            CONFIG_FILE.touch()
            print(f"Created configuration file: {CONFIG_FILE}") # Inform user
    except OSError as e:
        print(f"Warning: Error creating configuration path {CONFIG_FILE}: {e}", file=sys.stderr)

def load_config() -> tuple[str | None, str]:
    """
    Loads configuration from the user's config file. Does NOT prompt.
    Returns: (api_key, llm_model)
    """
    _debug_print(f"Attempting to load config from: {CONFIG_FILE}")
    ensure_config_paths() # Make sure file exists

    # Load from the specific file, potentially overriding existing os.environ vars
    # This is important if the user somehow has system-wide vars set.
    load_dotenv(dotenv_path=CONFIG_FILE, override=True)

    api_key = os.getenv("OPENAI_API_KEY")
    llm_model = os.getenv("LLM_MODEL") # Load raw value first
    _debug_print(f"Loaded from env after load_dotenv - API Key Present: {bool(api_key)}, Model Raw: '{llm_model}'")

    # Handle empty string values from .env as None/Default
    if not api_key: # Catches None and ""
        api_key = None
    if not llm_model: # Catches None and ""
        _debug_print(f"LLM_MODEL not found or empty, using default: {DEFAULT_LLM_MODEL}")
        llm_model = DEFAULT_LLM_MODEL
    # else: # Model was found and not empty
    #    _debug_print(f"Using LLM_MODEL from config: {llm_model}")


    _debug_print(f"load_config returning - API Key Present: {bool(api_key)}, Model: '{llm_model}'")
    return api_key, llm_model

def save_config(api_key: str | None, llm_model: str):
    """
    Saves the provided configuration to the user's config file.
    Updates os.environ for the current process.
    """
    _debug_print(f"Attempting to save config to: {CONFIG_FILE}")
    ensure_config_paths()
    try:
        # Ensure model has a value before saving
        final_llm_model = llm_model if llm_model else DEFAULT_LLM_MODEL
        _debug_print(f"Saving - API Key: {'SET' if api_key else 'UNSET'}, Model: '{final_llm_model}'")

        # Use find_dotenv to get the reliable path for set/unset_key
        # Important: usecwd=False ensures it looks at the absolute path provided
        dotenv_path = find_dotenv(filename=str(CONFIG_FILE), raise_error_if_not_found=False, usecwd=False)
        if not dotenv_path or not Path(dotenv_path).exists():
             # If find_dotenv fails (e.g., empty file?), fallback to the explicit path
             dotenv_path = str(CONFIG_FILE)
             _debug_print(f"find_dotenv didn't find {CONFIG_FILE}, using direct path.")
        else:
             _debug_print(f"find_dotenv located config at: {dotenv_path}")


        # Save/Unset API Key
        if api_key:
            set_key(dotenv_path, "OPENAI_API_KEY", api_key, quote_mode="never")
            _debug_print(f"Set OPENAI_API_KEY in {dotenv_path}")
        else:
            # Only unset if the key exists in the file, prevents errors on clean files
            if os.getenv("OPENAI_API_KEY"): # Check current env *after* load_dotenv
                 unset_key(dotenv_path, "OPENAI_API_KEY")
                 _debug_print(f"Unset OPENAI_API_KEY in {dotenv_path}")
            else:
                 _debug_print(f"Skipped unsetting OPENAI_API_KEY (was not set).")

        # Always set/update the model
        set_key(dotenv_path, "LLM_MODEL", final_llm_model, quote_mode="never")
        _debug_print(f"Set LLM_MODEL='{final_llm_model}' in {dotenv_path}")

        # --- Crucial: Update os.environ for the *current* process ---
        # This ensures that if save_config is called mid-way (like in load_or_prompt),
        # subsequent calls to os.getenv() in the same run reflect the change.
        os.environ["OPENAI_API_KEY"] = api_key if api_key else ""
        os.environ["LLM_MODEL"] = final_llm_model
        _debug_print(f"Updated os.environ - API Key Present: {bool(os.environ.get('OPENAI_API_KEY'))}, Model: '{os.environ.get('LLM_MODEL')}'")
        # --- End Crucial Update ---

        print(f"Configuration saved to {CONFIG_FILE}") # User message
        return True
    except Exception as e:
        print(f"Error saving configuration to {CONFIG_FILE}: {e}", file=sys.stderr)
        # Print traceback for detailed debugging if needed
        # import traceback
        # traceback.print_exc()
        return False

def prompt_for_api_key_interactive() -> str | None:
    """Interactively prompts the user ONLY for the API key."""
    _debug_print("Prompting user for API key.")
    print("-" * 30)
    print(f"OpenAI API Key not found in {CONFIG_FILE}") # Be specific
    try:
        api_key_input = input("Please enter your OpenAI API Key (leave blank to skip AI features): ").strip()
        print("-" * 30) # Print separator after input
        if api_key_input:
            print("API Key provided.") # User feedback
            _debug_print("User provided API key.")
            return api_key_input
        else:
            print("Skipping AI features for this session as no API key was provided.") # User feedback
            _debug_print("User skipped providing API key.")
            return None
    except EOFError:
        print("\nInput interrupted. Skipping AI features.")
        print("-" * 30)
        _debug_print("Input interrupted (EOFError).")
        return None
    except Exception as e:
        print(f"\nError during input: {e}. Skipping AI features.")
        print("-" * 30)
        _debug_print(f"Input error: {e}")
        return None

def configure_settings_interactive():
    """Runs an interactive wizard to configure API key and model."""
    print("--- CodeSum Configuration ---")
    print(f"Editing configuration file: {CONFIG_FILE}") # Make it clear

    current_api_key, current_llm_model = load_config() # Load fresh values
    _debug_print(f"Loaded for configure wizard - API Key Present: {bool(current_api_key)}, Model: '{current_llm_model}'")


    print(f"\nCurrent OpenAI API Key: {'Set' if current_api_key else 'Not Set'}")
    print(f"Current LLM Model: {current_llm_model}")
    print("-" * 30)

    try:
        # Prompt for API Key
        api_key_prompt = f"Enter new OpenAI API Key (leave blank to {'keep current' if current_api_key else 'remain unset'}, type 'clear' to remove): "
        new_api_key_input = input(api_key_prompt).strip()

        final_api_key = current_api_key # Start with current value

        if new_api_key_input.lower() == 'clear':
            final_api_key = None
            print("API Key will be cleared.")
        elif new_api_key_input: # If user entered something non-blank and not 'clear'
            final_api_key = new_api_key_input
            print("API Key will be updated.")
        # else: User left blank, final_api_key remains current_api_key
        #     print("API Key remains unchanged.")

        # Prompt for Model
        model_prompt = f"Enter new LLM Model (leave blank to keep '{current_llm_model}'): "
        new_llm_model_input = input(model_prompt).strip()

        final_llm_model = current_llm_model # Start with current

        if new_llm_model_input:
            final_llm_model = new_llm_model_input
            print(f"LLM Model will be set to '{final_llm_model}'.")
        # else: User left blank, final_llm_model remains current_llm_model
        #     print(f"LLM Model remains '{final_llm_model}'.")


        # Ensure final_llm_model is never None or empty before saving
        if not final_llm_model:
             _debug_print("Final LLM model was empty/None, setting to default.")
             final_llm_model = DEFAULT_LLM_MODEL


        # Save the final configuration
        print("-" * 30)
        if save_config(final_api_key, final_llm_model):
            # No need to print success again, save_config does it.
            pass
        else:
            print("Configuration update failed.") # Should already be printed by save_config

    except EOFError:
        print("\nConfiguration cancelled.")
    except Exception as e:
        print(f"\nAn error occurred during configuration: {e}")

    print("--- Configuration End ---")


def load_or_prompt_config() -> tuple[str | None, str]:
    """
    Loads config. If API key is missing, prompts the user interactively
    and saves it if provided. Updates current session's environment.
    Returns the loaded/updated (api_key, llm_model).
    """
    _debug_print("Running load_or_prompt_config...")
    api_key, llm_model = load_config() # Load initial state from file/env
    _debug_print(f"Initial load result - API Key Present: {bool(api_key)}, Model: '{llm_model}'")

    # Check if the key is missing *after* attempting to load it
    key_is_missing = not api_key

    if key_is_missing:
        _debug_print("API key not found, entering prompt.")
        new_api_key = prompt_for_api_key_interactive() # Ask user
        if new_api_key:
            _debug_print("Prompt returned a new API key. Saving it.")
            # Save the newly entered key, preserving the loaded (or default) model
            if save_config(new_api_key, llm_model):
                 # IMPORTANT: Update the key variable for *this function's return value*
                 api_key = new_api_key
                 _debug_print("Successfully saved new key and updated session key variable.")
                 # os.environ was updated inside save_config
            else:
                 _debug_print("Failed to save the new API key.")
                 # api_key remains None
        # else: # User didn't provide a key when prompted
        #    _debug_print("Prompt did not return a new API key.")

    # Print status for the user AFTER potential prompt/save
    print(f"Using configuration file: {CONFIG_FILE}") # Good to remind user
    if api_key:
        # Don't print the key itself, just confirm it's set
        print(f"OpenAI API Key: Set")
        print(f"Using model: {llm_model}")
    else:
        print("OpenAI API Key: Not Set. AI features will be disabled.")

    _debug_print(f"load_or_prompt_config returning - API Key Present: {bool(api_key)}, Model: '{llm_model}'")
    return api_key, llm_model
```
---
## File: src/codesum/file_utils.py

```py
import os
from pathlib import Path
import pathspec
import sys
import mimetypes

# Consider making this configurable or loaded from a file in future
DEFAULT_IGNORE_LIST = [
    ".git", "venv", ".summary_files", "__pycache__",
    ".vscode", ".idea", "node_modules", "build", "dist",
    "*.pyc", "*.pyo", "*.egg-info", ".DS_Store",
    ".env"  # Also ignore local .env files if any
]


def is_text_file(file_path: Path) -> bool:
    """
    Determine if a file is a text file by analyzing content first, with smart fallbacks.
    """
    # Quick wins: definitely text extensions (minimal list)
    definitely_text = {'.txt', '.md', '.json',
                       '.xml', '.csv', '.log', '.ini', '.cfg'}
    if file_path.suffix.lower() in definitely_text:
        return True

    # Quick losses: definitely binary extensions
    definitely_binary = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.webp',
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv',
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',
        '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
        '.exe', '.dll', '.so', '.dylib', '.app',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
    }
    if file_path.suffix.lower() in definitely_binary:
        return False

    # For everything else (including .ts files), analyze the content
    return _analyze_file_content(file_path)


def _analyze_file_content(file_path: Path, sample_size: int = 8192) -> bool:
    """
    Analyze file content to determine if it's likely a text file.
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(sample_size)

        if not chunk:  # Empty file
            return True

        # Check for null bytes (strong indicator of binary)
        if b'\x00' in chunk:
            return False

        # Check for too many control characters (except common ones like \t, \n, \r)
        control_chars = sum(1 for byte in chunk if byte <
                            32 and byte not in (9, 10, 13))
        if control_chars > len(chunk) * 0.1:  # More than 10% control chars
            return False

        # Try to decode as UTF-8
        try:
            text = chunk.decode('utf-8')

            # Additional heuristics for text files:
            # Check for reasonable printable character ratio
            printable_chars = sum(
                1 for char in text if char.isprintable() or char.isspace())
            printable_ratio = printable_chars / len(text) if text else 1

            return printable_ratio > 0.7  # At least 70% printable characters

        except UnicodeDecodeError:
            # Try other common encodings
            for encoding in ['latin-1', 'ascii', 'utf-16']:
                try:
                    chunk.decode(encoding)
                    return True  # Successfully decoded with some encoding
                except UnicodeDecodeError:
                    continue

            return False  # Couldn't decode with any common encoding

    except (IOError, OSError):
        return False  # Can't read file, assume binary


def find_all_gitignore_files(directory: Path) -> list[tuple[Path, Path]]:
    """
    Finds all .gitignore files in the directory tree.
    Returns a list of tuples: (gitignore_file_path, directory_containing_gitignore)
    """
    gitignore_files = []
    base_dir = directory.resolve()

    try:
        for root, dirs, files in os.walk(base_dir):
            # Skip .git directories and other ignored directories early
            dirs[:] = [d for d in dirs if d not in [
                '.git', '__pycache__', '.summary_files']]

            if '.gitignore' in files:
                gitignore_path = Path(root) / '.gitignore'
                parent_dir = Path(root)
                gitignore_files.append((gitignore_path, parent_dir))
    except Exception as e:
        print(
            f"Warning: Error walking directory tree for .gitignore files: {e}", file=sys.stderr)

    return gitignore_files


def parse_all_gitignores(directory: Path = Path('.')) -> pathspec.PathSpec | None:
    """
    Parses all .gitignore files in the directory tree and combines their patterns.
    Each .gitignore file's patterns are adjusted to be relative to the base directory.
    """
    base_dir = directory.resolve()
    gitignore_files = find_all_gitignore_files(base_dir)

    if not gitignore_files:
        return None

    all_patterns = []

    for gitignore_path, gitignore_parent in gitignore_files:
        try:
            with open(gitignore_path, "r", encoding='utf-8') as f:
                lines = [line.strip() for line in f.read().splitlines()
                         if line.strip() and not line.strip().startswith('#')]

            if not lines:
                continue

            # Calculate the relative path from base_dir to the directory containing this .gitignore
            try:
                relative_to_base = gitignore_parent.relative_to(base_dir)
                prefix = str(relative_to_base.as_posix()) + \
                    "/" if relative_to_base != Path('.') else ""
            except ValueError:
                # This shouldn't happen if we're walking from base_dir, but just in case
                print(
                    f"Warning: .gitignore at {gitignore_path} is outside base directory", file=sys.stderr)
                continue

            # Adjust patterns to be relative to base_dir
            for line in lines:
                if prefix and not line.startswith('/'):
                    # For patterns that don't start with /, they apply to the directory
                    # containing the .gitignore and all subdirectories
                    adjusted_pattern = prefix + line
                elif line.startswith('/'):
                    # Patterns starting with / are relative to the directory containing the .gitignore
                    adjusted_pattern = prefix + line[1:]  # Remove leading /
                else:
                    # Root .gitignore or patterns that should apply globally
                    adjusted_pattern = line

                all_patterns.append(adjusted_pattern)

        except IOError as e:
            print(
                f"Warning: Could not read .gitignore file {gitignore_path}: {e}", file=sys.stderr)
        except Exception as e:
            print(
                f"Warning: Error parsing .gitignore file {gitignore_path}: {e}", file=sys.stderr)

    if all_patterns:
        try:
            return pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, all_patterns)
        except Exception as e:
            print(
                f"Warning: Error creating pathspec from combined .gitignore patterns: {e}", file=sys.stderr)
            return None

    return None


def parse_gitignore(directory: Path = Path('.')) -> pathspec.PathSpec | None:
    """
    Legacy function name - now parses all .gitignore files in the directory tree.
    Kept for backward compatibility.
    """
    return parse_all_gitignores(directory)


def build_tree(directory: Path, gitignore_specs: pathspec.PathSpec | None, ignore_list: list[str]):
    """Builds a nested dictionary representing the directory structure, respecting ignores."""
    tree = {}
    # Use resolved absolute path for reliable comparison
    base_dir_path = Path(directory).resolve()

    for item_path in base_dir_path.rglob('*'):  # Use rglob for recursive walk
        try:
            # Get path relative to the starting directory
            relative_path = item_path.relative_to(base_dir_path)
            # Use posix for consistent matching
            relative_path_str = str(relative_path.as_posix())

            # 1. Check explicit ignore_list (faster check)
            if any(part in ignore_list for part in relative_path.parts):
                continue
            # Check if any parent dir is in ignore list (e.g. ignoring 'node_modules' should ignore everything inside)
            if any(ignore_item in parent.name for parent in relative_path.parents for ignore_item in ignore_list if parent != Path('.')):
                continue

            # 2. Check combined .gitignore patterns
            # Use as_posix() for pathspec matching, add trailing slash for dirs
            check_path = relative_path_str + '/' if item_path.is_dir() else relative_path_str
            if gitignore_specs and gitignore_specs.match_file(check_path):
                continue

            # 3. For files, check if they are text files
            if item_path.is_file() and not is_text_file(item_path):
                continue

            # If not ignored, add to tree
            current_level = tree
            parts = relative_path.parts

            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # Last part (file or dir name)
                    if item_path.is_file():
                        # Store full absolute path as value for files
                        current_level[part] = str(item_path)
                    elif item_path.is_dir():
                        # Ensure directory entry exists, could be empty
                        current_level = current_level.setdefault(part, {})
                else:  # Intermediate directory part
                    current_level = current_level.setdefault(part, {})

        except PermissionError:
            # print(f"Warning: Permission denied accessing {item_path}", file=sys.stderr)
            continue  # Skip files/dirs we can't access
        except Exception as e:
            print(
                f"Warning: Error processing path {item_path}: {e}", file=sys.stderr)
            continue

    return tree


def build_tree_with_folders(directory: Path, gitignore_specs: pathspec.PathSpec | None, ignore_list: list[str]):
    """Builds a nested dictionary representing the directory structure, including folders with files."""
    tree = {}
    # Use resolved absolute path for reliable comparison
    base_dir_path = Path(directory).resolve()

    # First, collect all files
    for item_path in base_dir_path.rglob('*'):
        try:
            # Get path relative to the starting directory
            relative_path = item_path.relative_to(base_dir_path)
            # Use posix for consistent matching
            relative_path_str = str(relative_path.as_posix())

            # 1. Check explicit ignore_list (faster check)
            if any(part in ignore_list for part in relative_path.parts):
                continue
            # Check if any parent dir is in ignore list
            if any(ignore_item in parent.name for parent in relative_path.parents for ignore_item in ignore_list if parent != Path('.')):
                continue

            # 2. Check combined .gitignore patterns
            check_path = relative_path_str + '/' if item_path.is_dir() else relative_path_str
            if gitignore_specs and gitignore_specs.match_file(check_path):
                continue

            # 3. For files, check if they are text files
            if item_path.is_file() and not is_text_file(item_path):
                continue

            # If not ignored and is a file, add to tree
            if item_path.is_file():
                current_level = tree
                parts = relative_path.parts

                for i, part in enumerate(parts):
                    if i == len(parts) - 1:  # Last part (file name)
                        # Store full absolute path as value for files
                        current_level[part] = str(item_path)
                    else:  # Intermediate directory part
                        current_level = current_level.setdefault(part, {})

        except PermissionError:
            continue  # Skip files/dirs we can't access
        except Exception as e:
            print(
                f"Warning: Error processing path {item_path}: {e}", file=sys.stderr)
            continue

    # Now filter out empty folders (folders that contain no files in their entire subtree)
    def _filter_empty_folders(tree_node: dict) -> dict:
        """Recursively remove empty folders from the tree."""
        filtered = {}
        for key, value in tree_node.items():
            if isinstance(value, dict):
                # This is a folder, recursively filter it
                filtered_subtree = _filter_empty_folders(value)
                # Only include the folder if it contains files after filtering
                if filtered_subtree:
                    filtered[key] = filtered_subtree
            else:
                # This is a file, keep it
                filtered[key] = value
        return filtered

    return _filter_empty_folders(tree)


def flatten_tree(tree, prefix=''):
    """Flattens the tree for display, ensuring files come before subdirs at each level."""
    items = []
    # Process files at the current level first, sorted alphabetically
    files_at_level = {}
    dirs_at_level = {}

    for key, value in tree.items():
        if isinstance(value, dict):
            dirs_at_level[key] = value
        else:
            files_at_level[key] = value

    # Add sorted files
    for key, full_path in sorted(files_at_level.items()):
        display_name = f"{prefix}{key}"
        items.append((display_name, full_path))  # (display name, full path)

    # Then recurse into sorted subdirectories
    for key, sub_tree in sorted(dirs_at_level.items()):
        dir_prefix = f"{prefix}{key}/"
        items.extend(flatten_tree(sub_tree, prefix=dir_prefix))

    return items


def flatten_tree_with_folders(tree, prefix='', folder_paths=None, expanded_folders=None):
    """
    Flattens the tree for display, including folders.
    Returns list of tuples: (display_name, path, is_folder, full_path_if_file)
    """
    if folder_paths is None:
        folder_paths = {}
    if expanded_folders is None:
        expanded_folders = set()
        
    items = []
    # Process files and folders at the current level, sorted alphabetically
    files_at_level = {}
    dirs_at_level = {}

    for key, value in tree.items():
        if isinstance(value, dict):
            dirs_at_level[key] = value
        else:
            files_at_level[key] = value

    # Add sorted files
    for key, full_path in sorted(files_at_level.items()):
        display_name = f"{prefix}{key}"
        items.append((display_name, f"{prefix}{key}", False, full_path))  # (display name, path, is_folder, full_path)

    # Add sorted folders
    for key, sub_tree in sorted(dirs_at_level.items()):
        folder_path = f"{prefix}{key}"
        display_name = f"{prefix}{key}/"
        is_expanded = folder_path in expanded_folders
        items.append((display_name, folder_path, True, None))  # (display name, path, is_folder, full_path)
        
        # If folder is expanded, recurse into it
        if is_expanded:
            items.extend(flatten_tree_with_folders(sub_tree, prefix=f"{prefix}{key}/", 
                                                 folder_paths=folder_paths, 
                                                 expanded_folders=expanded_folders))

    return items


def flatten_tree_with_folders_collapsed(tree, prefix='', folder_paths=None, collapsed_folders=None):
    """
    Flattens the tree for display, including folders, with collapsed state tracking.
    For folders that contain only one file, skips the folder and shows only the file.
    Returns list of tuples: (display_name, path, is_folder, full_path_if_file)
    """
    if folder_paths is None:
        folder_paths = {}
    if collapsed_folders is None:
        collapsed_folders = set()
        
    items = []
    # Process files and folders at the current level, sorted alphabetically
    files_at_level = {}
    dirs_at_level = {}

    for key, value in tree.items():
        if isinstance(value, dict):
            dirs_at_level[key] = value
        else:
            files_at_level[key] = value

    # Add sorted files
    for key, full_path in sorted(files_at_level.items()):
        display_name = f"{prefix}{key}"
        items.append((display_name, f"{prefix}{key}", False, full_path))  # (display name, path, is_folder, full_path)

    # Add sorted folders
    for key, sub_tree in sorted(dirs_at_level.items()):
        folder_path = f"{prefix}{key}"
        
        # Check if this folder contains only one file and no subdirectories
        if _folder_has_single_file(sub_tree):
            # Skip the folder and show only the file with the folder path as prefix
            for sub_key, sub_value in sub_tree.items():
                if not isinstance(sub_value, dict):  # This is the single file
                    display_name = f"{prefix}{key}/{sub_key}"
                    items.append((display_name, f"{prefix}{key}/{sub_key}", False, sub_value))  # Show as file, not folder
                    break
        else:
            # Show folder normally
            display_name = f"{prefix}{key}/"
            is_collapsed = folder_path in collapsed_folders
            items.append((display_name, folder_path, True, None))  # (display name, path, is_folder, full_path)
            
            # If folder is NOT collapsed, recurse into it
            if not is_collapsed:
                items.extend(flatten_tree_with_folders_collapsed(sub_tree, prefix=f"{prefix}{key}/", 
                                                     folder_paths=folder_paths, 
                                                     collapsed_folders=collapsed_folders))

    return items


def _folder_has_single_file(folder_tree: dict) -> bool:
    """
    Check if a folder contains only one file and no subdirectories.
    """
    file_count = 0
    dir_count = 0
    
    for key, value in folder_tree.items():
        if isinstance(value, dict):
            # This is a subdirectory
            dir_count += 1
        else:
            # This is a file
            file_count += 1
    
    # Return True only if there's exactly one file and no subdirectories
    return file_count == 1 and dir_count == 0


def _tree_contains_files(tree: dict) -> bool:
    """Check if a tree structure contains any files (not just empty folders)."""
    for key, value in tree.items():
        if isinstance(value, dict):
            # This is a subdirectory, check recursively
            if _tree_contains_files(value):
                return True
        else:
            # This is a file
            return True
    return False



def get_tree_output(directory: Path = Path('.'), gitignore_specs: pathspec.PathSpec | None = None, ignore_list: list[str] = DEFAULT_IGNORE_LIST) -> str:
    """Generates a string representation of the directory tree, respecting all .gitignore files."""
    output_lines = [".\n"]

    def walk_recursive(current_path: Path, level: int):
        try:
            entries = sorted(os.listdir(current_path))
        except OSError:
            return  # Cannot list dir

        indent = ' ' * (4 * level)
        for entry in entries:
            entry_path = current_path / entry
            relative_entry_path = entry_path.relative_to(directory.resolve())
            relative_entry_str = str(relative_entry_path.as_posix())

            # Check ignore list first
            if any(part in ignore_list for part in relative_entry_path.parts):
                continue

            # Check combined gitignore patterns
            check_path = relative_entry_str + '/' if entry_path.is_dir() else relative_entry_str
            if gitignore_specs and gitignore_specs.match_file(check_path):
                continue

            # For files, check if they are text files
            if entry_path.is_file() and not is_text_file(entry_path):
                continue

            # If not ignored, add to output and recurse if dir
            output_lines.append(f"{indent}|-- {entry}\n")
            if entry_path.is_dir():
                walk_recursive(entry_path, level + 1)

    walk_recursive(directory.resolve(), 0)
    return "".join(output_lines)

```
---
## File: src/codesum/folder_utils.py

```py
import os
from pathlib import Path


def collect_files_in_folder(folder_path: str, tree: dict) -> list[str]:
    """
    Recursively collect all file paths within a folder from the tree structure.
    
    Args:
        folder_path: The path of the folder to collect files from (e.g., 'src/codesum')
        tree: The tree structure dictionary
        
    Returns:
        List of absolute file paths within the folder
    """
    # Navigate to the folder in the tree
    parts = folder_path.split('/')
    current_level = tree
    
    # Navigate through the tree to find the folder
    for part in parts:
        if part and part in current_level:
            current_level = current_level[part]
        else:
            # Folder not found in tree
            return []
    
    # Collect all files recursively from this point
    file_paths = []
    _collect_files_recursive(current_level, file_paths)
    return file_paths


def _collect_files_recursive(tree_node: dict, file_paths: list[str]):
    """Helper function to recursively collect file paths."""
    for key, value in tree_node.items():
        if isinstance(value, dict):
            # This is a subdirectory, recurse into it
            _collect_files_recursive(value, file_paths)
        else:
            # This is a file, add its path
            file_paths.append(value)  # value is the absolute path string


def find_parent_folder_path(file_path: str, options: list) -> str | None:
    """
    Find the parent folder path of a file from the options list.

    Args:
        file_path: The path string of the file (e.g., 'src/codesum/tui.py')
        options: The list of tuples (display_name, path, is_folder, full_path)

    Returns:
        The parent folder path if found, otherwise None
    """
    # Extract the directory part from the file path
    if '/' not in file_path:
        return None  # File is at root, no parent folder

    parent_path = '/'.join(file_path.split('/')[:-1])

    # Look for this parent path in the options list
    for display_name, path, is_folder, full_path in options:
        if is_folder and path == parent_path:
            return path

    # If not found, try progressively shorter parent paths
    while '/' in parent_path:
        for display_name, path, is_folder, full_path in options:
            if is_folder and path == parent_path:
                return path
        parent_path = '/'.join(parent_path.split('/')[:-1])

    return None


def collect_all_subfolders(folder_path: str, tree: dict) -> list[str]:
    """
    Recursively collect all subfolder paths within a folder from the tree structure.

    Args:
        folder_path: The path of the folder to collect subfolders from (e.g., 'src/codesum')
        tree: The tree structure dictionary

    Returns:
        List of folder paths (including the root folder_path itself)
    """
    # Navigate to the folder in the tree
    parts = folder_path.split('/')
    current_level = tree

    # Navigate through the tree to find the folder
    for part in parts:
        if part and part in current_level:
            current_level = current_level[part]
        else:
            # Folder not found in tree
            return []

    # Collect all subfolders recursively from this point
    folder_paths = [folder_path]  # Include the root folder itself
    _collect_subfolders_recursive(current_level, folder_path, folder_paths)
    return folder_paths


def _collect_subfolders_recursive(tree_node: dict, current_path: str, folder_paths: list[str]):
    """Helper function to recursively collect subfolder paths."""
    for key, value in tree_node.items():
        if isinstance(value, dict):
            # This is a subdirectory
            subfolder_path = f"{current_path}/{key}"
            folder_paths.append(subfolder_path)
            # Recurse into it
            _collect_subfolders_recursive(value, subfolder_path, folder_paths)
```
---
## File: src/codesum/openai_utils.py

```py
import os
import sys
from openai import OpenAI, RateLimitError, APIError, APITimeoutError
from pathlib import Path
import tiktoken # Import tiktoken

# Conditional import for importlib.resources
if sys.version_info < (3, 9):
    import importlib_resources
    pkg_resources = importlib_resources
else:
    import importlib.resources as pkg_resources


def _load_prompt(prompt_filename: str) -> str:
    """Loads a prompt template from the package data."""
    try:
        # Use importlib.resources to access package data reliably
        resource_path = pkg_resources.files("codesum") / "prompts" / prompt_filename
        return resource_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        err_msg = f"Error: Prompt file '{prompt_filename}' not found in package data."
        print(err_msg, file=sys.stderr)
        return err_msg # Return error message as fallback prompt content
    except Exception as e:
        err_msg = f"Error reading prompt file '{prompt_filename}': {e}"
        print(err_msg, file=sys.stderr)
        return err_msg # Return error message as fallback prompt content


def generate_summary(client: OpenAI, model: str, file_content: str) -> str:
    """Generates a code summary using the OpenAI API."""
    if not client:
        return "Error: OpenAI client not available."

    system_prompt = _load_prompt("system_summary.md")
    if system_prompt.startswith("Error:"):
        return system_prompt # Return error if prompt loading failed

    print("Waiting for summary. This may take a few minutes...")
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": file_content}
            ],
            max_tokens=2500, # Consider making this configurable
            temperature=0.3 # Lower temperature for more focused summaries
        )
        summary = completion.choices[0].message.content
        return summary if summary else "Error: Empty summary received from API."
    except RateLimitError:
         print("Error: OpenAI API rate limit exceeded. Please try again later.", file=sys.stderr)
         return "Error: API rate limit exceeded."
    except APITimeoutError:
         print("Error: OpenAI API request timed out. Please try again later.", file=sys.stderr)
         return "Error: API request timed out."
    except APIError as e:
        print(f"Error: OpenAI API returned an error: {e}", file=sys.stderr)
        return f"Error: OpenAI API error: {e}"
    except Exception as e:
        print(f"Error calling OpenAI API for summary: {e}", file=sys.stderr)
        return f"Error generating summary: {e}"


def generate_readme(client: OpenAI, model: str, compressed_summary: str) -> str:
    """Generates a README.md file content using the OpenAI API."""
    if not client:
        return "Error: OpenAI client not available."

    system_prompt = _load_prompt("system_readme.md")
    if system_prompt.startswith("Error:"):
        return f"# README Generation Error\n\n{system_prompt}" # Return error

    print("Generating updated README.md file...")
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": compressed_summary}
            ],
            max_tokens=1500, # Consider making this configurable
            temperature=0.5 # Slightly higher temp for creative README
        )
        readme_content = completion.choices[0].message.content
        return readme_content if readme_content else "# README Generation Error\n\nEmpty content received from API."
    except RateLimitError:
         print("Error: OpenAI API rate limit exceeded. Cannot generate README.", file=sys.stderr)
         return "# README Generation Error\n\nAPI rate limit exceeded."
    except APITimeoutError:
         print("Error: OpenAI API request timed out. Cannot generate README.", file=sys.stderr)
         return "# README Generation Error\n\nAPI request timed out."
    except APIError as e:
        print(f"Error: OpenAI API returned an error during README generation: {e}", file=sys.stderr)
        return f"# README Generation Error\n\nOpenAI API error:\n```\n{e}\n```"
    except Exception as e:
        print(f"Error calling OpenAI API for README: {e}", file=sys.stderr)
        return f"# README Generation Error\n\nAn error occurred:\n```\n{e}\n```"

def compress_single_file(client: OpenAI, model: str, file_path: str, file_content: str) -> str:
    """Generates a compressed summary for a single file using the OpenAI API."""
    if not client:
        return "Error: OpenAI client not available."

    system_prompt = _load_prompt("system_summary.md")
    if system_prompt.startswith("Error:"):
        return system_prompt # Return error if prompt loading failed

    try:
        # Create a prompt that includes the file path context
        user_prompt = f"File: {file_path}\n\n{file_content}"

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500, # Limit for per-file summaries
            temperature=0.3 # Lower temperature for more focused summaries
        )
        summary = completion.choices[0].message.content
        return summary if summary else "Error: Empty summary received from API."
    except RateLimitError:
         print(f"Error: OpenAI API rate limit exceeded while compressing {file_path}", file=sys.stderr)
         return "Error: API rate limit exceeded."
    except APITimeoutError:
         print(f"Error: OpenAI API request timed out while compressing {file_path}", file=sys.stderr)
         return "Error: API request timed out."
    except APIError as e:
        print(f"Error: OpenAI API returned an error while compressing {file_path}: {e}", file=sys.stderr)
        return f"Error: OpenAI API error: {e}"
    except Exception as e:
        print(f"Error calling OpenAI API for {file_path}: {e}", file=sys.stderr)
        return f"Error generating summary: {e}"


def count_tokens(text: str, encoding_name: str = "o200k_base") -> int:
    """
    Counts the number of tokens in a text string using tiktoken.
    Defaults to "o200k_base" encoding suitable for gpt-4o and other recent models.
    """
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        num_tokens = len(encoding.encode(text))
        return num_tokens
    except Exception as e:
        print(f"Error using tiktoken to count tokens (encoding: {encoding_name}): {e}", file=sys.stderr)
        # Fallback or re-raise, for now return 0 or -1 to indicate error
        return -1 # Or 0, or raise an exception
```
---
## File: src/codesum/summary_utils.py [AI Compressed]

The `summary_utils.py` module is designed to manage and generate code summaries, including both full and AI-compressed summaries, for a given project directory. It handles file and directory management, reading and writing configuration data, and interacting with an AI client for generating compressed summaries.

### Constants
- **SUMMARY_DIR_NAME**: Directory name for storing summary files.
- **CUSTOM_IGNORE_FILENAME**: Filename for custom ignore patterns.
- **CODE_SUMMARY_FILENAME**: Filename for the full code summary.
- **COMPRESSED_SUMMARY_FILENAME**: Filename for the compressed code summary.
- **SELECTION_FILENAME**: Filename for storing previous file selections.
- **COLLAPSED_FOLDERS_FILENAME**: Filename for storing collapsed folder paths.
- **METADATA_SUFFIX**: Suffix for metadata files.
- **SELECTION_CONFIGS_FILENAME**: Filename for storing selection configurations.

### Functions

- **get_summary_dir(base_dir: Path = Path('.')) -> Path**: Returns the path to the summary directory within the base directory.

- **create_hidden_directory(base_dir: Path = Path('.'))**: Creates the summary directory and a custom ignore file if they don't exist.

- **read_previous_selection(base_dir: Path = Path('.')) -> list[str]**: Reads previously selected file paths from a JSON file, removing non-existent files and updating the stored selection.

- **write_previous_selection(selected_files: list[str], base_dir: Path = Path('.'))**: Writes the list of selected file paths to a JSON file.

- **create_code_summary(selected_files: list[str], base_dir: Path = Path('.'), compressed_files: list[str] = None, client: OpenAI | None = None, llm_model: str = None)**: Generates a code summary file, using AI for compressed summaries if specified.

- **create_compressed_summary(selected_files: list[str], client: OpenAI | None, llm_model: str, base_dir: Path = Path('.'))**: Creates a compressed summary markdown file using AI for non-main files.

- **copy_summary_to_clipboard(base_dir: Path = Path('.'))**: Copies the content of the local code summary to the clipboard.

- **read_previous_collapsed_folders(base_dir: Path = Path('.')) -> list[str] | None**: Reads previously collapsed folder paths from a JSON file.

- **write_previous_collapsed_folders(collapsed_folders: list[str], base_dir: Path = Path('.'))**: Writes the list of collapsed folder paths to a JSON file.

- **read_selection_configs(base_dir: Path = Path('.')) -> dict**: Reads saved selection configurations from a JSON file.

- **write_selection_configs(configs: dict, base_dir: Path = Path('.'))**: Writes selection configurations to a JSON file.

- **save_selection_config(name: str, selected_files: list[str], compressed_files: list[str], base_dir: Path = Path('.'))**: Saves a named selection configuration.

- **load_selection_config(name: str, base_dir: Path = Path('.')) -> tuple[list[str], list[str]] | None**: Loads a named selection configuration.

- **delete_selection_config(name: str, base_dir: Path = Path('.'))**: Deletes a named selection configuration.

- **rename_selection_config(old_name: str, new_name: str, base_dir: Path = Path('.'))**: Renames a selection configuration.

### Notes
- The module heavily relies on file I/O operations for reading and writing JSON files.
- It uses the `openai_utils` module for AI interactions, specifically for generating compressed summaries.
- Error handling is implemented for file operations, with warnings printed to `sys.stderr`.
- The module provides functionality to manage and cache summaries using metadata files to avoid redundant AI calls.

---
## File: src/codesum/tui.py

```py
import curses
import os
import sys
import signal
from pathlib import Path
import pathspec # For type hint

# Import our new folder_utils
from . import folder_utils
from . import openai_utils

# --- Helper Functions ---

# Token count cache to avoid recalculating for the same files
_token_cache = {}

def _get_file_token_count(file_path: str) -> int:
    """
    Get token count for a file, with caching to improve performance.
    Returns -1 if file cannot be read or processed.
    """
    try:
        file_path_obj = Path(file_path)
        
        # Check if file exists and get its modification time for cache key
        if not file_path_obj.exists():
            return -1
            
        mtime = file_path_obj.stat().st_mtime
        cache_key = (file_path, mtime)
        
        # Return cached result if available
        if cache_key in _token_cache:
            return _token_cache[cache_key]
        
        # Read file and count tokens
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            content = f.read()
        
        token_count = openai_utils.count_tokens(content)
        
        # Cache the result
        _token_cache[cache_key] = token_count
        return token_count
        
    except Exception:
        return -1

def _format_token_count(token_count: int) -> str:
    """Format token count for display."""
    if token_count < 0:
        return "(?)"
    elif token_count < 1000:
        return f"{token_count}"
    elif token_count < 1000000:
        return f"{token_count/1000:.1f}k"
    else:
        return f"{token_count/1000000:.1f}M"

def _is_single_file_at_root(tree: dict) -> bool:
    """
    Check if there's only one file at the root level with no subdirectories.
    This is used to determine if we should skip folder display.
    """
    file_count = 0
    dir_count = 0
    
    for key, value in tree.items():
        if isinstance(value, dict):
            # This is a directory
            dir_count += 1
            # Check if this directory has any contents
            if _count_files_in_tree(value) > 0 or len(value) > 0:
                # If there are subdirectories or files, it's not a simple case
                return False
        else:
            # This is a file
            file_count += 1
    
    # Return True only if there's exactly one file and no directories
    return file_count == 1 and dir_count == 0

def _count_files_in_tree(tree: dict) -> int:
    """Count the total number of files in a tree structure."""
    count = 0
    for key, value in tree.items():
        if isinstance(value, dict):
            # This is a directory, recurse into it
            count += _count_files_in_tree(value)
        else:
            # This is a file
            count += 1
    return count

def _flatten_single_file_tree(tree: dict) -> list[tuple]:
    """
    Flatten a tree structure when there's only one file.
    Returns a list with a single tuple: (filename, path, is_folder, full_path)
    """
    def _find_single_file(tree: dict, prefix: str = '') -> tuple:
        """Find the single file in the tree and return its info."""
        for key, value in tree.items():
            if isinstance(value, dict):
                # This is a directory, recurse into it
                result = _find_single_file(value, f"{prefix}{key}/")
                if result:
                    return result
            else:
                # This is the single file
                return (key, prefix + key, False, value)  # (display_name, path, is_folder, full_path)
        return None
    
    single_file = _find_single_file(tree)
    return [single_file] if single_file else []

# --- Helper Function to Check Terminal Color Support ---
def check_color_support():
    """Checks if the terminal likely supports colors."""
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    try:
        # Use curses to check color support after initscr
        # This check is more reliable within the curses context
        curses.start_color()
        if curses.has_colors():
            # Optional: Check for minimum number of colors/pairs if needed
            # print(f"Colors supported: {curses.COLORS}, Pairs: {curses.COLOR_PAIRS}")
            return True
        return False
    except curses.error:
        # Error likely means no color support or terminal issue
        return False
    # Note: This check inside check_color_support might be problematic
    # if called *before* curses.wrapper. It's better to check *inside*
    # the curses-managed function (draw_menu).

# --- Constants for Curses Colors ---
COLOR_PAIR_DEFAULT = 0
COLOR_PAIR_FOLDER_PATH = 1  # Blue for folder paths in file listings
COLOR_PAIR_FOLDER_ITEM = 2  # Green for expanded folder items in the list
COLOR_PAIR_COLLAPSED_FOLDER = 6  # Darker green for collapsed folder items in the list
COLOR_PAIR_FILE = 3
COLOR_PAIR_STATUS = 4 # For the cursor line background/foreground
COLOR_PAIR_HIGHLIGHT = 5 # For the cursor line background/foreground
COLOR_PAIR_SELECTED = 7  # Gold/yellow for selected files (X marker)
COLOR_PAIR_COMPRESSED = 8  # Different color for compressed summary marker (★)


# --- Main Selection Function ---
def select_files(
    directory: Path,
    previous_selection: list[str],
    gitignore_specs: pathspec.PathSpec | None,
    ignore_list: list[str]
) -> tuple[list[str], list[str]]:
    """Interactively selects files using curses, showing folders and coloring paths."""

    # Import build_tree and flatten_tree locally to avoid circular dependency potential
    # OR restructure file_utils slightly if needed. Assume they are importable.
    from . import file_utils
    from . import summary_utils

    tree = file_utils.build_tree_with_folders(directory, gitignore_specs, ignore_list)
    
    # Determine if we're in single file mode (only one file at root level)
    single_file_mode = _is_single_file_at_root(tree)
    
    # Track folder states: expanded/collapsed and paths
    collapsed_folders = set()  # Set of folder paths that are collapsed
    folder_paths = {}  # Map of folder display paths to actual paths

    # Read previous collapsed folder states
    previous_collapsed = summary_utils.read_previous_collapsed_folders(directory)
    if previous_collapsed is not None:
        collapsed_folders = set(previous_collapsed)
    # If no previous state, all folders are expanded by default (empty collapsed_folders set)
    
    # flatten_tree_with_folders returns (display_name, path, is_folder, full_path_if_file) tuples
    flattened_items = file_utils.flatten_tree_with_folders_collapsed(tree, collapsed_folders=collapsed_folders, folder_paths=folder_paths)

    # Convert previous_selection (absolute paths) to a set for efficient lookup
    # Ensure paths from previous selection are resolved absolute paths
    selected_paths = set(str(Path(p).resolve()) for p in previous_selection)

    # Track files marked for compressed summaries (using ★ marker)
    compressed_paths = set()  # Set of absolute paths to generate compressed summaries for

    # Prepare options for curses: (display_name, path, is_folder, full_path)
    options = [(display, path, is_folder, full_path) for display, path, is_folder, full_path in flattened_items]
    
    # Store the directory path for display in the header
    directory_path = str(directory.resolve())
    
    # Store reference to tree for folder operations
    tree_ref = tree

    # --- Curses Main Logic (Inner Function) ---
    def _curses_main(stdscr):
        nonlocal selected_paths, collapsed_folders, compressed_paths # Allow modification of the set from parent scope
        curses.curs_set(0)  # Hide cursor
        current_page = 0
        current_pos = 0
        has_color = False # Determined after curses init
        show_help = False  # Track whether help popup is visible
        show_configs = False  # Track whether configs popup is visible
        interrupted = False  # Track if Ctrl+C was pressed

        # Enable mouse support
        try:
            curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        except:
            pass  # Mouse support not available, continue without it

        # Set up signal handler for Ctrl+C
        def signal_handler(signum, frame):
            nonlocal interrupted
            interrupted = True

        # Install the signal handler
        old_handler = signal.signal(signal.SIGINT, signal_handler)

        # Calculate total token count for selected files (excluding compressed files)
        def _calculate_total_tokens():
            total = 0
            for file_path in selected_paths:
                # Don't count tokens for files marked for compressed summary
                if file_path not in compressed_paths:
                    token_count = _get_file_token_count(file_path)
                    if token_count > 0:
                        total += token_count
            return total

        # Initialize colors safely
        try:
             if curses.has_colors():
                  has_color = True
                  curses.use_default_colors() # Try for transparent background
                  # Define color pairs (adjust colors as desired)
                  curses.init_pair(COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, -1)
                  curses.init_pair(COLOR_PAIR_FOLDER_PATH, curses.COLOR_BLUE, -1)  # Blue for folder paths
                  curses.init_pair(COLOR_PAIR_FOLDER_ITEM, curses.COLOR_GREEN, -1)  # Green for expanded folder items
                  curses.init_pair(COLOR_PAIR_COLLAPSED_FOLDER, curses.COLOR_GREEN, -1)  # Darker green for collapsed folder items
                  curses.init_pair(COLOR_PAIR_FILE, curses.COLOR_WHITE, -1)
                  curses.init_pair(COLOR_PAIR_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE) # Status bar
                  curses.init_pair(COLOR_PAIR_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_CYAN) # Highlight line
                  curses.init_pair(COLOR_PAIR_SELECTED, curses.COLOR_YELLOW, -1)  # Gold/yellow for selected (X)
                  curses.init_pair(COLOR_PAIR_COMPRESSED, curses.COLOR_MAGENTA, -1)  # Magenta for compressed (★)
             else:
                  # Define fallback pairs for monochrome if needed, though A_REVERSE works
                  curses.init_pair(COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, curses.COLOR_BLACK)
                  curses.init_pair(COLOR_PAIR_FOLDER_PATH, curses.COLOR_WHITE, curses.COLOR_BLACK)
                  curses.init_pair(COLOR_PAIR_FOLDER_ITEM, curses.COLOR_WHITE, curses.COLOR_BLACK)
                  curses.init_pair(COLOR_PAIR_COLLAPSED_FOLDER, curses.COLOR_WHITE, curses.COLOR_BLACK)  # For collapsed folders in monochrome
                  curses.init_pair(COLOR_PAIR_FILE, curses.COLOR_WHITE, curses.COLOR_BLACK)
                  curses.init_pair(COLOR_PAIR_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
                  curses.init_pair(COLOR_PAIR_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_WHITE)
        except curses.error as e:
             # Color setup failed, proceed without color
             # print(f"Color setup error: {e}") # Debug
             has_color = False


        while True:
            # Check if interrupted by Ctrl+C
            if interrupted:
                # Save collapsed folder states before quitting
                summary_utils.write_previous_collapsed_folders(list(collapsed_folders), directory)
                selected_paths = None  # Signal cancellation
                break

            h, w = stdscr.getmaxyx()

            # Calculate header lines based on width
            if w >= 40:
                header_lines = 3  # Typical case
            elif w >= 30:
                header_lines = 4  # Token info on separate line
            else:
                header_lines = 3  # Minimal mode

            page_size = max(1, h - header_lines - 1) # Rows available for options

            items_on_current_page = min(page_size, len(options) - current_page * page_size)
            max_pos_on_page = items_on_current_page - 1 if items_on_current_page > 0 else 0

            # Adjust current_pos if it's out of bounds due to resize or page change
            if current_pos > max_pos_on_page:
                 current_pos = max_pos_on_page
            if current_pos < 0 : # Ensure current_pos is not negative
                 current_pos = 0

            # --- Draw Menu ---
            total_tokens = _calculate_total_tokens()
            if show_help:
                _draw_help_popup(stdscr, has_color)
            elif show_configs:
                _draw_configs_popup(stdscr, has_color, directory)
            else:
                _draw_menu(stdscr, options, selected_paths, compressed_paths, collapsed_folders, current_page, current_pos, page_size, has_color, directory_path, total_tokens)

            # --- Get Key ---
            try:
                 stdscr.timeout(50)  # Reduced from 100ms to 50ms for better responsiveness
                 key = stdscr.getch()
                 if key == -1:  # No key pressed
                     continue
            except curses.error: # Handle interrupt during getch maybe?
                 key = -1 # Treat as no key press
                 continue

            # --- Key Handling ---
            current_abs_index = current_page * page_size + current_pos
            total_options = len(options)
            total_pages = (total_options + page_size - 1) // page_size if page_size > 0 else 1

            # Handle mouse events
            if key == curses.KEY_MOUSE:
                try:
                    _, mx, my, _, bstate = curses.getmouse()

                    # Debug: Uncomment to see mouse events
                    # stdscr.addstr(0, 0, f"Mouse: bstate={hex(bstate)} my={my} mx={mx}"[:w-1])
                    # stdscr.refresh()

                    # Calculate which line was clicked
                    # Determine header offset
                    if w >= 40 and len(f"CodeSum - {directory_path}") + len(f"Tokens: {_format_token_count(total_tokens)}") + 3 <= w:
                        header_offset = 3
                    elif w >= 30:
                        header_offset = 4
                    else:
                        header_offset = 3

                    # Handle scroll wheel events (anywhere on screen)
                    # Scroll wheel up (BUTTON4)
                    if bstate & curses.BUTTON4_PRESSED:
                        if current_pos > 0:
                            current_pos -= 1
                        elif current_page > 0:
                            current_page -= 1
                            h_new, _ = stdscr.getmaxyx()
                            page_size_new = max(1, h_new - header_offset - 1)
                            items_on_prev_page = min(page_size_new, total_options - current_page * page_size_new)
                            current_pos = items_on_prev_page - 1 if items_on_prev_page > 0 else 0

                    # Scroll wheel down - try multiple button codes for compatibility
                    # 0x200000 = BUTTON5_PRESSED on most systems
                    # 0x8000000 = alternative encoding on some terminals
                    elif bstate & 0x200000 or bstate & 0x8000000 or (hasattr(curses, 'BUTTON5_PRESSED') and bstate & curses.BUTTON5_PRESSED):
                        if current_pos < max_pos_on_page:
                            current_pos += 1
                        elif current_page < total_pages - 1:
                            current_page += 1
                            current_pos = 0

                    # Check if click was in the content area (below headers)
                    elif my >= header_offset:
                        clicked_idx = my - header_offset

                        # Check if click is within current page items
                        if 0 <= clicked_idx < items_on_current_page:
                            # Left click - select item
                            if bstate & curses.BUTTON1_CLICKED:
                                # Move cursor to clicked item
                                current_pos = clicked_idx

                                # Get the item details
                                clicked_abs_index = current_page * page_size + clicked_idx
                                if 0 <= clicked_abs_index < total_options:
                                    display_name, path, is_folder, full_path = options[clicked_abs_index]

                                    if is_folder:
                                        # Toggle folder collapse
                                        if path in collapsed_folders:
                                            collapsed_folders.discard(path)
                                        else:
                                            collapsed_folders.add(path)
                                        # Rebuild options
                                        flattened_items = file_utils.flatten_tree_with_folders_collapsed(tree_ref, collapsed_folders=collapsed_folders, folder_paths=folder_paths)
                                        options[:] = [(display, p, is_fold, f_path) for display, p, is_fold, f_path in flattened_items]
                                    else:
                                        # Toggle file selection
                                        resolved_path = str(Path(full_path).resolve())
                                        if resolved_path in selected_paths:
                                            selected_paths.remove(resolved_path)
                                        else:
                                            selected_paths.add(resolved_path)

                    continue
                except:
                    pass  # Ignore mouse errors

            # Help popup handling
            if key == ord('h') or key == ord('H') or key == ord('?'):
                show_help = not show_help
                show_configs = False  # Close configs if open
                continue

            # Configs popup handling
            if key == ord('m') or key == ord('M'):
                show_configs = not show_configs
                show_help = False  # Close help if open
                continue

            # If help is shown, any other key closes it
            if show_help:
                show_help = False
                continue

            # If configs popup is shown, handle it separately
            if show_configs:
                # Handle configs popup interactions
                result = _handle_configs_input(stdscr, key, directory, has_color, selected_paths, compressed_paths)
                if result == "close":
                    show_configs = False
                elif result and isinstance(result, tuple):
                    # Load a configuration
                    loaded_selected, loaded_compressed = result
                    # Update current selection
                    selected_paths.clear()
                    compressed_paths.clear()
                    selected_paths.update(str(Path(p).resolve()) for p in loaded_selected)
                    compressed_paths.update(str(Path(p).resolve()) for p in loaded_compressed)
                    show_configs = False
                continue

            if key == ord('q') or key == 27: # Quit
                # Save collapsed folder states before quitting
                summary_utils.write_previous_collapsed_folders(list(collapsed_folders), directory)
                # Optionally ask for confirmation? For now, just quit.
                # We need to return the *original* selection if user quits.
                # Let's return None to signal cancellation.
                selected_paths = None # Signal cancellation
                break
            elif key == ord('a') or key == ord('A'):  # Select/Deselect all
                # Get all file paths from options
                all_file_paths = set(str(Path(full_path).resolve()) for _, _,
                                    is_folder, full_path in options if not is_folder and full_path)
                # Check if all currently visible files are selected (use subset instead of equality)
                if all_file_paths and all_file_paths.issubset(selected_paths):
                    # All visible files are selected, so deselect only the visible ones
                    selected_paths.difference_update(all_file_paths)
                else:
                    # Otherwise, select all visible files
                    if not single_file_mode:
                        selected_paths.update(all_file_paths)
                    # In single file mode, just select the one file
                    elif all_file_paths:
                        selected_paths.update(all_file_paths)

            elif key == ord(' '): # Toggle selection
                if 0 <= current_abs_index < total_options:
                    display_name, path, is_folder, full_path = options[current_abs_index]
                    if is_folder:
                        # Toggle folder collapse
                        if path in collapsed_folders:
                            collapsed_folders.discard(path)
                        else:
                            collapsed_folders.add(path)
                        # Rebuild options with new collapsed state
                        flattened_items = file_utils.flatten_tree_with_folders_collapsed(tree_ref, collapsed_folders=collapsed_folders, folder_paths=folder_paths)
                        options[:] = [(display, p, is_fold, f_path) for display, p, is_fold, f_path in flattened_items]
                    else:
                        # Toggle file selection
                        resolved_path = str(Path(full_path).resolve()) # Use resolved path for set
                        # If file is currently marked for compressed summary, remove that marking
                        if resolved_path in compressed_paths:
                            compressed_paths.remove(resolved_path)
                        # Toggle regular selection
                        if resolved_path in selected_paths:
                            selected_paths.remove(resolved_path)
                        else:
                            selected_paths.add(resolved_path)
                        # Move down after selection (optional usability enhancement)
                        if current_pos < max_pos_on_page:
                             current_pos += 1
                        elif current_page < total_pages - 1:
                              current_page += 1
                              current_pos = 0

            elif key == ord('s') or key == ord('S'):  # Toggle compressed summary
                if 0 <= current_abs_index < total_options:
                    display_name, path, is_folder, full_path = options[current_abs_index]
                    if not is_folder:  # Only works on files
                        resolved_path = str(Path(full_path).resolve())
                        if resolved_path in compressed_paths:
                            compressed_paths.remove(resolved_path)
                        else:
                            # Add to compressed paths and ensure it's also selected
                            compressed_paths.add(resolved_path)
                            selected_paths.add(resolved_path)
                        # Move down after marking (optional usability enhancement)
                        if current_pos < max_pos_on_page:
                             current_pos += 1
                        elif current_page < total_pages - 1:
                              current_page += 1
                              current_pos = 0

            elif key == ord('f') or key == ord('F'):  # Toggle folder selection
                if 0 <= current_abs_index < total_options:
                    display_name, path, is_folder, full_path = options[current_abs_index]

                    # Determine the folder to work with
                    target_folder_path = None
                    if is_folder:
                        target_folder_path = path
                    else:
                        # File is selected, find its parent folder
                        target_folder_path = folder_utils.find_parent_folder_path(path, options)

                    if target_folder_path:
                        # Get all files in the target folder
                        folder_files = folder_utils.collect_files_in_folder(target_folder_path, tree_ref)
                        # Convert to resolved paths for comparison
                        resolved_folder_files = set(str(Path(f).resolve()) for f in folder_files)

                        # Check if all files in folder are currently selected
                        all_selected = resolved_folder_files.issubset(selected_paths)

                        if all_selected:
                            # Deselect all files in folder
                            selected_paths.difference_update(resolved_folder_files)
                        else:
                            # Select all files in folder
                            selected_paths.update(resolved_folder_files)

            elif key == ord('e') or key == ord('E'):  # Expand all folders recursively
                if 0 <= current_abs_index < total_options:
                    display_name, path, is_folder, full_path = options[current_abs_index]

                    # Determine the folder to work with
                    target_folder_path = None
                    if is_folder:
                        target_folder_path = path
                    else:
                        # File is selected, find its parent folder
                        target_folder_path = folder_utils.find_parent_folder_path(path, options)

                    if target_folder_path:
                        # Get all subfolders within the target folder
                        all_subfolders = folder_utils.collect_all_subfolders(target_folder_path, tree_ref)
                        # Remove all these folders from collapsed_folders to expand them
                        for subfolder in all_subfolders:
                            collapsed_folders.discard(subfolder)
                        # Rebuild options with new collapsed state
                        flattened_items = file_utils.flatten_tree_with_folders_collapsed(tree_ref, collapsed_folders=collapsed_folders, folder_paths=folder_paths)
                        options[:] = [(display, p, is_fold, f_path) for display, p, is_fold, f_path in flattened_items]

            elif key == ord('c') or key == ord('C'):  # Collapse all child folders recursively
                if 0 <= current_abs_index < total_options:
                    display_name, path, is_folder, full_path = options[current_abs_index]

                    # Determine the folder to work with
                    target_folder_path = None
                    if is_folder:
                        target_folder_path = path
                    else:
                        # File is selected, find its parent folder
                        target_folder_path = folder_utils.find_parent_folder_path(path, options)

                    if target_folder_path:
                        # Get all subfolders within the target folder
                        all_subfolders = folder_utils.collect_all_subfolders(target_folder_path, tree_ref)
                        # Add all subfolders to collapsed_folders EXCEPT the target folder itself
                        for subfolder in all_subfolders:
                            if subfolder != target_folder_path:
                                collapsed_folders.add(subfolder)
                        # Rebuild options with new collapsed state
                        flattened_items = file_utils.flatten_tree_with_folders_collapsed(tree_ref, collapsed_folders=collapsed_folders, folder_paths=folder_paths)
                        options[:] = [(display, p, is_fold, f_path) for display, p, is_fold, f_path in flattened_items]

            elif key == curses.KEY_UP:
                if current_pos > 0:
                    current_pos -= 1
                elif current_page > 0:
                    current_page -= 1
                    # Calc items on new prev page
                    h_new, w_new = stdscr.getmaxyx()
                    page_size_new = max(1, h_new - 4)
                    items_on_prev_page = min(page_size_new, total_options - current_page * page_size_new)
                    current_pos = items_on_prev_page - 1 if items_on_prev_page > 0 else 0

            elif key == curses.KEY_DOWN:
                if current_pos < max_pos_on_page:
                    current_pos += 1
                elif current_page < total_pages - 1:
                    current_page += 1
                    current_pos = 0

            elif key == curses.KEY_RIGHT:  # Next folder
                # Find the next folder after current position
                next_folder_abs_index = None
                for i in range(current_abs_index + 1, total_options):
                    if options[i][2]:  # is_folder
                        next_folder_abs_index = i
                        break

                if next_folder_abs_index is not None:
                    # Calculate which page and position the folder is on
                    current_page = next_folder_abs_index // page_size
                    current_pos = next_folder_abs_index % page_size

            elif key == curses.KEY_LEFT:  # Previous folder
                # Find the previous folder before current position
                prev_folder_abs_index = None
                for i in range(current_abs_index - 1, -1, -1):
                    if options[i][2]:  # is_folder
                        prev_folder_abs_index = i
                        break

                if prev_folder_abs_index is not None:
                    # Calculate which page and position the folder is on
                    current_page = prev_folder_abs_index // page_size
                    current_pos = prev_folder_abs_index % page_size

            elif key == curses.KEY_PPAGE:  # Page Up
                 if current_page > 0:
                    current_page -= 1
                    current_pos = 0

            elif key == curses.KEY_NPAGE:  # Page Down
                 if current_page < total_pages - 1:
                    current_page += 1
                    current_pos = 0

            elif key == 10 or key == curses.KEY_ENTER:  # Confirm selection
                # Save collapsed folder states before confirming
                summary_utils.write_previous_collapsed_folders(list(collapsed_folders), directory)
                break # Exit loop, selected_paths holds the final set

            elif key == curses.KEY_RESIZE: # Handle terminal resize
                 # Recalculate page size and potentially current_pos
                 # The loop automatically handles redraw on next iteration
                 # Ensure current_pos remains valid is handled at top of loop
                 pass

        # Restore original signal handler before exiting
        signal.signal(signal.SIGINT, old_handler)

        # Return the set of selected paths and compressed paths (or None if cancelled)
        return (selected_paths, compressed_paths)

    # --- Draw Help Popup Helper (Inner Function) ---
    def _draw_help_popup(stdscr, has_color):
        """Draw a centered help popup with all keyboard shortcuts."""
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        help_content = [
            "╔═══════════════════════════════════════════════════════════╗",
            "║                   KEYBOARD SHORTCUTS                      ║",
            "╠═══════════════════════════════════════════════════════════╣",
            "║ Navigation:                                               ║",
            "║   ↑/↓           Move up/down                              ║",
            "║   ←/→           Jump to previous/next folder              ║",
            "║   PgUp/PgDn     Page up/down                              ║",
            "║                                                           ║",
            "║ Selection:                                                ║",
            "║   SPACE         Toggle file selection ([X] marker)        ║",
            "║   S             Toggle compressed summary ([★] marker)    ║",
            "║   F             Toggle all files in current folder        ║",
            "║   A             Select/deselect all files                 ║",
            "║   E             Expand all folders (recursive)            ║",
            "║   C             Collapse child folders (recursive)        ║",
            "║                                                           ║",
            "║ Configurations:                                           ║",
            "║   M             Manage selection configurations (CRUD)    ║",
            "║                                                           ║",
            "║ Mouse Support:                                            ║",
            "║   Click         Select item and toggle selection          ║",
            "║   Scroll        Scroll up/down through items              ║",
            "║                                                           ║",
            "║ Actions:                                                  ║",
            "║   ENTER         Confirm selection                         ║",
            "║   Q/ESC         Quit without saving                       ║",
            "║   H/?           Show this help                            ║",
            "║                                                           ║",
            "║ Tips:                                                     ║",
            "║   • [X] = Selected (gold), [★] = Compressed (magenta)    ║",
            "║   • Compressed files are auto-selected                    ║",
            "║   • Save/load configurations with M key                   ║",
            "║   • Token counts shown for individual files               ║",
            "╚═══════════════════════════════════════════════════════════╝",
            "",
            "Press any key to close this help..."
        ]

        # Calculate popup dimensions
        popup_height = len(help_content)
        popup_width = max(len(line) for line in help_content)

        # Center the popup
        start_y = max(0, (h - popup_height) // 2)
        start_x = max(0, (w - popup_width) // 2)

        # Draw the popup
        try:
            for i, line in enumerate(help_content):
                y = start_y + i
                if y < h:
                    # Truncate line if it doesn't fit
                    display_line = line[:w-1] if start_x == 0 else line
                    if has_color:
                        # Use highlight color for the header
                        if i == 1:
                            stdscr.addstr(y, start_x, display_line[:min(len(display_line), w-start_x-1)],
                                        curses.color_pair(COLOR_PAIR_HIGHLIGHT) | curses.A_BOLD)
                        else:
                            stdscr.addstr(y, start_x, display_line[:min(len(display_line), w-start_x-1)])
                    else:
                        if i == 1:
                            stdscr.addstr(y, start_x, display_line[:min(len(display_line), w-start_x-1)],
                                        curses.A_REVERSE | curses.A_BOLD)
                        else:
                            stdscr.addstr(y, start_x, display_line[:min(len(display_line), w-start_x-1)])
        except curses.error:
            pass  # Ignore errors if terminal is too small

        stdscr.refresh()

    # --- Draw Configs Popup Helper (Inner Function) ---
    def _draw_configs_popup(stdscr, has_color, base_dir):
        """Draw a popup for managing selection configurations."""
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        configs = summary_utils.read_selection_configs(base_dir)
        config_names = sorted(configs.keys())

        help_content = [
            "╔═══════════════════════════════════════════════════════════╗",
            "║              SELECTION CONFIGURATIONS                     ║",
            "╠═══════════════════════════════════════════════════════════╣",
            "",
            "Saved Configurations:",
            ""
        ]

        if config_names:
            for i, name in enumerate(config_names, 1):
                config = configs[name]
                num_files = len(config.get("selected_files", []))
                num_compressed = len(config.get("compressed_files", []))
                help_content.append(f"  {i}. {name} ({num_files} files, {num_compressed} compressed)")
        else:
            help_content.append("  (No saved configurations)")

        help_content.extend([
            "",
            "╠═══════════════════════════════════════════════════════════╣",
            "║ Actions:                                                  ║",
            "║   S             Save current selection (prompts for name) ║",
            "║   L             Load configuration (enter number)         ║",
            "║   R             Rename configuration (enter number)       ║",
            "║   D             Delete configuration (enter number)       ║",
            "║   ESC/M         Close this menu                           ║",
            "╚═══════════════════════════════════════════════════════════╝",
            "",
            "Press a key to perform an action..."
        ])

        # Calculate popup dimensions
        popup_height = len(help_content)
        popup_width = max(len(line) for line in help_content)

        # Center the popup
        start_y = max(0, (h - popup_height) // 2)
        start_x = max(0, (w - popup_width) // 2)

        # Draw the popup
        try:
            for i, line in enumerate(help_content):
                y = start_y + i
                if y < h:
                    # Truncate line if it doesn't fit
                    display_line = line[:w-1] if start_x == 0 else line
                    if has_color:
                        # Use highlight color for the header
                        if i == 1:
                            stdscr.addstr(y, start_x, display_line[:min(len(display_line), w-start_x-1)],
                                        curses.color_pair(COLOR_PAIR_HIGHLIGHT) | curses.A_BOLD)
                        else:
                            stdscr.addstr(y, start_x, display_line[:min(len(display_line), w-start_x-1)])
                    else:
                        if i == 1:
                            stdscr.addstr(y, start_x, display_line[:min(len(display_line), w-start_x-1)],
                                        curses.A_REVERSE | curses.A_BOLD)
                        else:
                            stdscr.addstr(y, start_x, display_line[:min(len(display_line), w-start_x-1)])
        except curses.error:
            pass  # Ignore errors if terminal is too small

        stdscr.refresh()

    def _handle_configs_input(stdscr, key, base_dir, has_color, selected_paths, compressed_paths):
        """Handle keyboard input in the configs popup. Returns 'close', tuple of (selected, compressed), or None."""
        configs = summary_utils.read_selection_configs(base_dir)
        config_names = sorted(configs.keys())

        # Close on ESC or M
        if key == 27 or key == ord('m') or key == ord('M'):
            return "close"

        # Save current selection
        elif key == ord('s') or key == ord('S'):
            stdscr.timeout(-1)  # Disable timeout - wait indefinitely for input
            curses.echo()
            curses.curs_set(1)
            try:
                h, w = stdscr.getmaxyx()
                # Clear the bottom area
                stdscr.addstr(h-2, 0, " " * (w-1))
                stdscr.addstr(h-1, 0, " " * (w-1))
                stdscr.addstr(h-2, 0, "Enter configuration name: ")
                stdscr.refresh()
                name = stdscr.getstr(h-2, 26, 50).decode('utf-8').strip()
                if name:
                    summary_utils.save_selection_config(name, sorted(list(selected_paths)), sorted(list(compressed_paths)), base_dir)
                    stdscr.addstr(h-1, 0, f"Saved configuration '{name}'! Press any key...")
                    stdscr.refresh()
                    stdscr.timeout(-1)
                    stdscr.getch()  # Wait for keypress
            except Exception as e:
                # Show error message
                try:
                    stdscr.addstr(h-1, 0, f"Error: {str(e)}. Press any key...")
                    stdscr.refresh()
                    stdscr.timeout(-1)
                    stdscr.getch()
                except:
                    pass
            finally:
                curses.noecho()
                curses.curs_set(0)
                stdscr.timeout(50)  # Re-enable timeout
            return None

        # Load configuration
        elif key == ord('l') or key == ord('L'):
            if not config_names:
                return None
            stdscr.timeout(-1)  # Disable timeout
            curses.echo()
            curses.curs_set(1)
            try:
                h, w = stdscr.getmaxyx()
                stdscr.addstr(h-2, 0, " " * (w-1))
                stdscr.addstr(h-1, 0, " " * (w-1))
                stdscr.addstr(h-2, 0, f"Enter config number (1-{len(config_names)}): ")
                stdscr.refresh()
                num_str = stdscr.getstr(h-2, 40, 10).decode('utf-8').strip()
                if num_str.isdigit():
                    num = int(num_str)
                    if 1 <= num <= len(config_names):
                        config_name = config_names[num - 1]
                        result = summary_utils.load_selection_config(config_name, base_dir)
                        if result:
                            stdscr.timeout(50)  # Re-enable timeout
                            return result
            except Exception as e:
                try:
                    stdscr.addstr(h-1, 0, f"Error: {str(e)}. Press any key...")
                    stdscr.refresh()
                    stdscr.getch()
                except:
                    pass
            finally:
                curses.noecho()
                curses.curs_set(0)
                stdscr.timeout(50)  # Re-enable timeout
            return None

        # Delete configuration
        elif key == ord('d') or key == ord('D'):
            if not config_names:
                return None
            stdscr.timeout(-1)  # Disable timeout
            curses.echo()
            curses.curs_set(1)
            try:
                h, w = stdscr.getmaxyx()
                stdscr.addstr(h-2, 0, " " * (w-1))
                stdscr.addstr(h-1, 0, " " * (w-1))
                stdscr.addstr(h-2, 0, f"Enter config number to delete (1-{len(config_names)}): ")
                stdscr.refresh()
                num_str = stdscr.getstr(h-2, 50, 10).decode('utf-8').strip()
                if num_str.isdigit():
                    num = int(num_str)
                    if 1 <= num <= len(config_names):
                        config_name = config_names[num - 1]
                        summary_utils.delete_selection_config(config_name, base_dir)
                        stdscr.addstr(h-1, 0, f"Deleted configuration '{config_name}'! Press any key...")
                        stdscr.refresh()
                        stdscr.getch()
            except Exception as e:
                try:
                    stdscr.addstr(h-1, 0, f"Error: {str(e)}. Press any key...")
                    stdscr.refresh()
                    stdscr.getch()
                except:
                    pass
            finally:
                curses.noecho()
                curses.curs_set(0)
                stdscr.timeout(50)  # Re-enable timeout
            return None

        # Rename configuration
        elif key == ord('r') or key == ord('R'):
            if not config_names:
                return None
            stdscr.timeout(-1)  # Disable timeout
            curses.echo()
            curses.curs_set(1)
            try:
                h, w = stdscr.getmaxyx()
                stdscr.addstr(h-3, 0, " " * (w-1))
                stdscr.addstr(h-2, 0, " " * (w-1))
                stdscr.addstr(h-1, 0, " " * (w-1))
                stdscr.addstr(h-3, 0, f"Enter config number to rename (1-{len(config_names)}): ")
                stdscr.refresh()
                num_str = stdscr.getstr(h-3, 50, 10).decode('utf-8').strip()
                if num_str.isdigit():
                    num = int(num_str)
                    if 1 <= num <= len(config_names):
                        old_name = config_names[num - 1]
                        stdscr.addstr(h-2, 0, f"Enter new name for '{old_name}': ")
                        stdscr.refresh()
                        new_name = stdscr.getstr(h-2, 30 + len(old_name), 50).decode('utf-8').strip()
                        if new_name:
                            if summary_utils.rename_selection_config(old_name, new_name, base_dir):
                                stdscr.addstr(h-1, 0, f"Renamed '{old_name}' to '{new_name}'! Press any key...")
                                stdscr.refresh()
                                stdscr.getch()
            except Exception as e:
                try:
                    stdscr.addstr(h-1, 0, f"Error: {str(e)}. Press any key...")
                    stdscr.refresh()
                    stdscr.getch()
                except:
                    pass
            finally:
                curses.noecho()
                curses.curs_set(0)
                stdscr.timeout(50)  # Re-enable timeout
            return None

        return None

    # --- Draw Menu Helper (Inner Function) ---
    def _draw_menu(stdscr, options, selected_paths, compressed_paths, collapsed_folders, current_page, current_pos, page_size, has_color, directory_path, total_tokens):
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        # Enforce minimum width
        MIN_WIDTH = 20
        if w < MIN_WIDTH:
            try:
                stdscr.addstr(0, 0, "Window too narrow!")[:w-1]
                stdscr.addstr(1, 0, "Please resize.")[:w-1]
            except curses.error: pass
            return

        # Instructions - adapt based on width
        title_base = "CodeSum"
        token_info = f"Tokens: {_format_token_count(total_tokens)}"

        # Adaptive instructions based on width - simplified to show basic functionality
        if w >= 80:
            instructions = "[SPACE] Select | [↑↓] Navigate | [ENTER] Confirm | [H/?] Help | [Q] Quit"
            title = f"{title_base} - {directory_path}"
        elif w >= 60:
            instructions = "[SPC] Select | [↑↓] Nav | [Enter] OK | [H] Help | [Q] Quit"
            # Truncate directory path if needed
            max_path_len = w - len(title_base) - 4
            if len(directory_path) > max_path_len:
                title = f"{title_base} - ...{directory_path[-(max_path_len-3):]}"
            else:
                title = f"{title_base} - {directory_path}"
        else:  # w >= 20 (minimum)
            instructions = "[SPC] Sel [H] Help [Q] Quit"
            title = title_base

        try:
            # Draw title
            stdscr.addstr(0, 0, title[:w-1].ljust(min(len(title), w-1)))

            # Show token count right-aligned if there's space (at least 40 chars total)
            if w >= 40 and len(title) + len(token_info) + 3 <= w:
                stdscr.addstr(0, w - len(token_info) - 1, token_info)
            elif w >= 30:
                # Show token info on separate line if space allows
                stdscr.addstr(1, 0, token_info[:w-1].ljust(min(len(token_info), w-1)))

            # Draw instructions (will be on line 1 or 2 depending on token info placement)
            instr_line = 1 if w >= 40 and len(title) + len(token_info) + 3 <= w else 2 if w >= 30 else 1
            stdscr.addstr(instr_line, 0, instructions[:w-1].ljust(min(len(instructions), w-1)))

            # Draw separator
            sep_line = instr_line + 1
            stdscr.addstr(sep_line, 0, "-" * (w - 1))
        except curses.error:
            pass  # Ignore errors if window too small

        # Calculate display slice
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(options))
        current_options_page = options[start_idx:end_idx]

        # Calculate header offset based on width
        if w >= 40 and len(title) + len(token_info) + 3 <= w:
            header_lines = 3  # title/token on same line, instructions, separator
        elif w >= 30:
            header_lines = 4  # title, token, instructions, separator
        else:
            header_lines = 3  # title, instructions, separator

        # Display file/folder list
        for idx, (display_name, path, is_folder, full_path) in enumerate(current_options_page):
            y_pos = idx + header_lines # Start below headers

            is_selected = False
            if is_folder:
                # For folders, show as expanded/collapsed
                is_selected = path not in collapsed_folders
            else:
                # For files, check if selected
                resolved_path = str(Path(full_path).resolve()) # Use resolved path for checking selection
                is_selected = resolved_path in selected_paths
            is_highlighted = idx == current_pos

            # Determine attributes
            attr = curses.A_NORMAL
            folder_path_attr = curses.A_NORMAL
            folder_item_attr = curses.A_NORMAL
            file_attr = curses.A_NORMAL

            if has_color:
                default_pair = curses.color_pair(COLOR_PAIR_DEFAULT)
                folder_path_pair = curses.color_pair(COLOR_PAIR_FOLDER_PATH)
                folder_item_pair = curses.color_pair(COLOR_PAIR_FOLDER_ITEM)
                collapsed_folder_pair = curses.color_pair(COLOR_PAIR_COLLAPSED_FOLDER)
                file_pair = curses.color_pair(COLOR_PAIR_FILE)
                highlight_pair = curses.color_pair(COLOR_PAIR_HIGHLIGHT)
                attr |= default_pair
                folder_path_attr |= folder_path_pair
                folder_item_attr |= folder_item_pair
                file_attr |= file_pair
                if is_highlighted:
                    # Apply highlight pair to all parts of the line
                    attr = highlight_pair | curses.A_BOLD # Make highlighted bold
                    folder_path_attr = highlight_pair | curses.A_BOLD
                    folder_item_attr = highlight_pair | curses.A_BOLD
                    file_attr = highlight_pair | curses.A_BOLD
            elif is_highlighted:
                 attr = curses.A_REVERSE # Fallback highlight for monochrome
                 folder_path_attr = curses.A_REVERSE
                 folder_item_attr = curses.A_REVERSE
                 file_attr = curses.A_REVERSE


            # Render line components
            if is_folder:
                # Show folder with +/- indicator
                indicator = "[-]" if is_selected else "[+]"
                # Use shorter indicators for narrow windows
                if w < 40:
                    checkbox = f"{indicator[1]} " # Just use - or +
                else:
                    checkbox = f"{indicator} "
                token_suffix = ""

                # Use different color for collapsed folders
                if has_color and not is_selected:  # Collapsed folder (is_selected = path not in collapsed_folders)
                    folder_item_attr = collapsed_folder_pair | curses.A_DIM  # Use the collapsed folder color with dim effect for darker green
                    if is_highlighted:
                        folder_item_attr = highlight_pair | curses.A_BOLD
                elif has_color and is_highlighted:
                    folder_item_attr = highlight_pair | curses.A_BOLD  # Highlight expanded folders when selected
                elif has_color and is_selected:  # Expanded folder
                    folder_item_attr = folder_item_pair  # Use the expanded folder color
            else:
                # Show file with checkbox/markers and token count
                resolved_path = str(Path(full_path).resolve())
                is_compressed = resolved_path in compressed_paths

                # Use shorter checkbox for narrow windows
                if w < 40:
                    if is_compressed:
                        checkbox = "★ "  # Star for compressed
                    elif is_selected:
                        checkbox = "X "  # X for selected
                    else:
                        checkbox = "  "  # Empty
                else:
                    if is_compressed:
                        checkbox = "[★] "  # Star for compressed
                    elif is_selected:
                        checkbox = "[X] "  # X for selected
                    else:
                        checkbox = "[ ] "  # Empty

                # Show token count only if there's enough width
                if full_path and w >= 50:
                    token_count = _get_file_token_count(full_path)
                    token_suffix = f" ({_format_token_count(token_count)})"
                else:
                    token_suffix = ""

            prefix = f"{checkbox}"
            # Determine prefix color based on state
            prefix_attr = attr
            if not is_folder and has_color:
                resolved_path = str(Path(full_path).resolve())
                if resolved_path in compressed_paths:
                    prefix_attr = curses.color_pair(COLOR_PAIR_COMPRESSED) | (curses.A_BOLD if is_highlighted else curses.A_NORMAL)
                elif resolved_path in selected_paths:
                    prefix_attr = curses.color_pair(COLOR_PAIR_SELECTED) | (curses.A_BOLD if is_highlighted else curses.A_NORMAL)
            suffix_len = len(token_suffix)
            max_name_width = w - len(prefix) - suffix_len - 1 # Max width for the display name

            # Ensure max_name_width is positive
            if max_name_width < 3:
                max_name_width = 3

            # Truncate display name if necessary
            truncated_name = display_name
            if len(display_name) > max_name_width:
                if max_name_width <= 3:
                    truncated_name = display_name[:max_name_width]
                else:
                    # For narrow windows, show beginning; for wider, show end
                    if w < 40:
                        truncated_name = display_name[:max_name_width-1] + "…"
                    else:
                        truncated_name = "..." + display_name[-(max_name_width-3):] # Show end part

            # Draw prefix (with appropriate color)
            try:
                stdscr.addstr(y_pos, 0, prefix, prefix_attr)
            except curses.error: pass

            # Draw name (with potential color split)
            x_offset = len(prefix)
            last_slash_idx = truncated_name.rfind('/')
            name_end_pos = x_offset + len(truncated_name)
            try:
                if is_folder and has_color:
                    # Entire name is a folder item, use orange color
                    stdscr.addstr(y_pos, x_offset, truncated_name, folder_item_attr)
                elif has_color and last_slash_idx != -1:
                    # File with path, color the path part blue and file part white
                    path_part = truncated_name[:last_slash_idx + 1]
                    file_part = truncated_name[last_slash_idx + 1:]
                    stdscr.addstr(y_pos, x_offset, path_part, folder_path_attr)
                    # Check bounds before drawing file part
                    if x_offset + len(path_part) < w:
                         stdscr.addstr(y_pos, x_offset + len(path_part), file_part, file_attr)
                elif not is_folder and has_color:
                    # Entire name is a file, use white color
                    stdscr.addstr(y_pos, x_offset, truncated_name, file_attr)
                else:
                    # No color or no slash, draw whole name with base attr
                    stdscr.addstr(y_pos, x_offset, truncated_name, attr)
                
                # Draw token suffix if it exists (in dimmed style)
                if token_suffix and name_end_pos + len(token_suffix) < w:
                    # Use dimmed attribute for token count to make it less prominent
                    token_attr = attr | curses.A_DIM if has_color else attr | curses.A_DIM
                    stdscr.addstr(y_pos, name_end_pos, token_suffix, token_attr)
                    
            except curses.error:
                # Attempt to draw truncated version if full fails near edge
                try:
                     safe_name = truncated_name[:w-x_offset-suffix_len-1]
                     stdscr.addstr(y_pos, x_offset, safe_name, attr)
                     if token_suffix and x_offset + len(safe_name) + len(token_suffix) < w:
                         # Use dimmed attribute for token count in fallback case too
                         token_attr = attr | curses.A_DIM
                         stdscr.addstr(y_pos, x_offset + len(safe_name), token_suffix, token_attr)
                except curses.error: pass # Final fallback: ignore draw error


    # --- Run Curses ---
    final_selected_paths = None # Initialize to None (meaning cancelled or error)
    final_compressed_paths = None
    try:
         result = curses.wrapper(_curses_main)
         if result is not None: # Check if user confirmed (didn't quit)
             selected_set, compressed_set = result
             # Convert sets of absolute paths back to sorted lists
             final_selected_paths = sorted(list(selected_set))
             final_compressed_paths = sorted(list(compressed_set))
    except curses.error as e:
         # Clear screen attempts might fail if terminal is in bad state
         # os.system('cls' if os.name == 'nt' else 'clear') # Try clearing screen post-error
         print(f"\nTerminal error: {e}", file=sys.stderr)
         print("There was an issue initializing/running the text interface.", file=sys.stderr)
         print("This might be due to an incompatible terminal, running in an unsupported environment,", file=sys.stderr)
         print("or the terminal window being too small.", file=sys.stderr)
         # Indicate failure by returning None or empty list
    except Exception as e:
         print(f"\nAn unexpected error occurred during file selection: {e}", file=sys.stderr)
         # Indicate failure

    # Return the final selection (list of absolute paths) or empty lists if cancelled/error
    if final_selected_paths is not None and final_compressed_paths is not None:
        return (final_selected_paths, final_compressed_paths)
    else:
        return ([], [])
```
---
