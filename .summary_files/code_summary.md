Project Root: C:\Users\gthin\Github\codesum
Project Structure:
```
.
|-- .gitignore
|-- LICENSE
|-- README.md
|-- pyproject.toml
|-- release.sh
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
## File: src/codesum/app.py

```py
# src/codesum/app.py

import sys
import argparse # Import argparse
from pathlib import Path
from openai import OpenAI # Just for type hint

# Import from our modules
# Use explicit relative imports
from . import config
from . import file_utils
from . import tui
from . import summary_utils
from . import openai_utils

def main():
    """Main application entry point."""

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="Generate code summaries optimized for LLMs, with an interactive TUI."
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="Run the interactive configuration wizard for API key and model, then exit."
    )
    # Add other arguments here if needed in the future (e.g., --non-interactive, --output-dir)
    args = parser.parse_args()

    # --- Handle Configuration Mode ---
    if args.configure:
        config.configure_settings_interactive()
        sys.exit(0) # Exit after configuration

    # --- Normal Operation ---
    base_dir = Path('.').resolve() # Use current working directory as base
    print(f"Analyzing project root: {base_dir}")

    # 1. Load Configuration (will prompt for API key if missing)
    api_key, llm_model = config.load_or_prompt_config()

    # 2. Initialize OpenAI Client (if key provided)
    openai_client = None
    if api_key:
        try:
            openai_client = OpenAI(api_key=api_key)
            print("OpenAI client initialized.") # Add confirmation
        except Exception as e:
             print(f"Error initializing OpenAI client: {e}. AI features disabled.", file=sys.stderr)
             # Proceed without client, AI features will be disabled
    #else: # Already printed message in load_or_prompt_config
    #    print("AI features disabled (OpenAI API Key not provided/configured).")


    # 3. Prepare Project Directory Structure & Ignores
    summary_utils.create_hidden_directory(base_dir)
    gitignore_specs = file_utils.parse_gitignore(base_dir)
    ignore_list = file_utils.DEFAULT_IGNORE_LIST # Use default ignore list

    # 4. Load Previous Selection
    previous_selection = summary_utils.read_previous_selection(base_dir) # Expects/returns absolute paths

    # 5. Run Interactive File Selection
    print("Loading file selection interface...")
    # select_files expects absolute paths in previous_selection and returns absolute paths or empty list
    selected_files = tui.select_files(base_dir, previous_selection, gitignore_specs, ignore_list)

    if not selected_files:
        # Check if selection was cancelled (tui returns empty list now) or genuinely empty
        print("No files selected or selection cancelled. Exiting.")
        return

    print("\nSelected files:")
    # Make sure selected_files contains strings before processing
    if selected_files and isinstance(selected_files[0], str):
        for f_abs_str in selected_files:
            f_path = Path(f_abs_str)
            try:
                 # Display relative path for clarity
                 print(f"- {f_path.relative_to(base_dir).as_posix()}")
            except ValueError:
                 print(f"- {f_path}") # Fallback if not relative
    else:
        print("Error: Invalid selection data received from TUI.", file=sys.stderr)
        return # Exit if selection data is bad


    # 6. Save Current Selection (absolute paths)
    summary_utils.write_previous_selection(selected_files, base_dir)
    print(f"\nSelection saved to '{summary_utils.SUMMARY_DIR_NAME}/{summary_utils.SELECTION_FILENAME}'.")

    # 7. Create Local Code Summary (Full Content)
    summary_utils.create_code_summary(selected_files, base_dir)
    local_summary_path = summary_utils.get_summary_dir(base_dir) / summary_utils.CODE_SUMMARY_FILENAME
    if local_summary_path.exists():
        print(f"Local code summary (full content) created in '{local_summary_path}'.")
        try:
            with open(local_summary_path, "r", encoding='utf-8') as f:
                content = f.read()
            token_count = openai_utils.count_tokens(content)
            if token_count >= 0: # Check for valid count
                print(f"Tokens in '{summary_utils.CODE_SUMMARY_FILENAME}': {token_count}")
        except Exception as e:
            print(f"Error counting tokens for {local_summary_path}: {e}", file=sys.stderr)
    else:
        print(f"Local code summary file not found at '{local_summary_path}'.", file=sys.stderr)

    # 8. Copy to Clipboard
    summary_utils.copy_summary_to_clipboard(base_dir)

    # 9. Handle Optional AI Features
    if openai_client:
        try:
            # Ask about compressed summary
            generate_compressed_q = input("\nGenerate AI-powered compressed summary? (y/N): ").strip().lower()
            if generate_compressed_q == 'y':
                print("Generating compressed summary...") # Give feedback
                summary_utils.create_compressed_summary(selected_files, openai_client, llm_model, base_dir)
                compressed_summary_path = summary_utils.get_summary_dir(base_dir) / summary_utils.COMPRESSED_SUMMARY_FILENAME
                if compressed_summary_path.exists():
                    print(f"\nAI-powered compressed code summary created in '{compressed_summary_path}'.")
                    try:
                        with open(compressed_summary_path, "r", encoding='utf-8') as f:
                            content = f.read()
                        token_count = openai_utils.count_tokens(content)
                        if token_count >= 0: # Check for valid count
                            print(f"Tokens in '{summary_utils.COMPRESSED_SUMMARY_FILENAME}': {token_count}")
                    except Exception as e:
                        print(f"Error counting tokens for {compressed_summary_path}: {e}", file=sys.stderr)

                    # Ask about README generation (only if compressed summary was made and exists)
                    generate_readme_q = input("Generate/Update README.md using AI summary? (y/N): ").strip().lower()
                    if generate_readme_q == 'y':
                        print("Generating README...") # Give feedback
                        try:
                            # Reload content just in case, though it should be the same
                            with open(compressed_summary_path, "r", encoding='utf-8') as f:
                                compressed_summary_content = f.read()

                            if compressed_summary_content.strip():
                                readme_content = openai_utils.generate_readme(openai_client, llm_model, compressed_summary_content)
                                readme_file = base_dir / "README.md" # In project root
                                with open(readme_file, "w", encoding='utf-8') as f:
                                    f.write(readme_content)
                                print(f"\nUpdated '{readme_file}' successfully.")
                            else:
                                print("Compressed summary is empty. Skipping README generation.", file=sys.stderr)

                        except FileNotFoundError:
                            print(f"Error: Compressed summary file '{compressed_summary_path}' not found for README generation.", file=sys.stderr)
                        except Exception as e:
                            print(f"Error during README generation: {e}", file=sys.stderr)
                else:
                    print(f"AI-powered compressed summary file not found at '{compressed_summary_path}'. Skipping further AI steps.", file=sys.stderr)


        except EOFError:
             print("\nInput interrupted during AI feature prompts.")
        except Exception as e:
             print(f"\nAn error occurred during AI feature processing: {e}", file=sys.stderr)
    else:
        # Message about disabled AI features is now printed earlier during config load
        # We can add a reminder here if needed, but might be redundant.
        # print("\nSkipping AI features (OpenAI client not available/configured).")
        pass # No client, skip AI section

    print("\nProcess finished.")


if __name__ == "__main__":
    # This allows running 'python -m codesum.app'
    main()
```
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

# Consider making this configurable or loaded from a file in future
DEFAULT_IGNORE_LIST = [
    ".git", "venv", ".summary_files", "__pycache__",
    ".vscode", ".idea", "node_modules", "build", "dist",
    "*.pyc", "*.pyo", "*.egg-info", ".DS_Store",
    ".env" # Also ignore local .env files if any
]

def parse_gitignore(directory: Path = Path('.')) -> pathspec.PathSpec | None:
    """Parses .gitignore file in the specified directory."""
    gitignore_path = directory / ".gitignore"
    gitignore_specs = None
    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r", encoding='utf-8') as f:
                lines = [line for line in f.read().splitlines() if line.strip() and not line.strip().startswith('#')]
            if lines:
                gitignore_specs = pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, lines)
        except IOError as e:
            print(f"Warning: Could not read .gitignore file: {e}", file=sys.stderr)
        except Exception as e:
             print(f"Warning: Error parsing .gitignore patterns: {e}", file=sys.stderr)
    return gitignore_specs

def build_tree(directory: Path, gitignore_specs: pathspec.PathSpec | None, ignore_list: list[str]):
    """Builds a nested dictionary representing the directory structure, respecting ignores."""
    tree = {}
    base_dir_path = Path(directory).resolve() # Use resolved absolute path for reliable comparison

    for item_path in base_dir_path.rglob('*'): # Use rglob for recursive walk
        try:
            # Get path relative to the starting directory
            relative_path = item_path.relative_to(base_dir_path)
            relative_path_str = str(relative_path.as_posix()) # Use posix for consistent matching

            # 1. Check explicit ignore_list (faster check)
            if any(part in ignore_list for part in relative_path.parts):
                continue
            # Check if any parent dir is in ignore list (e.g. ignoring 'node_modules' should ignore everything inside)
            if any(ignore_item in parent.name for parent in relative_path.parents for ignore_item in ignore_list if parent != Path('.')):
                 continue


            # 2. Check .gitignore
            # Use as_posix() for pathspec matching, add trailing slash for dirs
            check_path = relative_path_str + '/' if item_path.is_dir() else relative_path_str
            if gitignore_specs and gitignore_specs.match_file(check_path):
                continue

            # If not ignored, add to tree
            current_level = tree
            parts = relative_path.parts

            for i, part in enumerate(parts):
                if i == len(parts) - 1: # Last part (file or dir name)
                    if item_path.is_file():
                        # Store full absolute path as value for files
                        current_level[part] = str(item_path)
                    elif item_path.is_dir():
                         # Ensure directory entry exists, could be empty
                         current_level = current_level.setdefault(part, {})
                else: # Intermediate directory part
                    current_level = current_level.setdefault(part, {})

        except PermissionError:
            # print(f"Warning: Permission denied accessing {item_path}", file=sys.stderr)
            continue # Skip files/dirs we can't access
        except Exception as e:
            print(f"Warning: Error processing path {item_path}: {e}", file=sys.stderr)
            continue

    return tree


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
        items.append((display_name, full_path)) # (display name, full path)

    # Then recurse into sorted subdirectories
    for key, sub_tree in sorted(dirs_at_level.items()):
        dir_prefix = f"{prefix}{key}/"
        items.extend(flatten_tree(sub_tree, prefix=dir_prefix))

    return items

def get_tree_output(directory: Path = Path('.'), gitignore_specs: pathspec.PathSpec | None = None, ignore_list: list[str] = DEFAULT_IGNORE_LIST) -> str:
    """Generates a string representation of the directory tree, respecting ignores."""
    output = ".\n"
    # We use os.walk here as it's often more efficient for simple listing
    # Need to re-implement the ignore logic within the walk loop

    start_dir = str(directory.resolve())

    for root, dirs, files in os.walk(start_dir, topdown=True):
        current_dir_path = Path(root)
        relative_dir_path = current_dir_path.relative_to(start_dir)
        level = len(relative_dir_path.parts)
        indent = ' ' * (4 * level)

        # Filter dirs based on ignore_list and gitignore BEFORE adding parent to output
        original_dirs = list(dirs) # Copy before modifying dirs[:]
        dirs[:] = [d for d in original_dirs if
                   d not in ignore_list and
                   not any(part in ignore_list for part in (relative_dir_path / d).parts) and
                   not (gitignore_specs and gitignore_specs.match_file(str((relative_dir_path / d).as_posix()) + '/'))
                  ]

        # Filter files based on ignore_list and gitignore
        filtered_files = [f for f in files if
                          f not in ignore_list and
                           not any(part in ignore_list for part in (relative_dir_path / f).parts) and
                          not (gitignore_specs and gitignore_specs.match_file(str((relative_dir_path / f).as_posix())))
                         ]

        # Combine and sort entries for the current level
        entries = sorted(dirs + filtered_files)

        for entry in entries:
             output += f"{indent}|-- {entry}\n"

        # Important: Stop os.walk from descending into ignored directories earlier
        # We already modified dirs[:] above based on ignores, so os.walk won't enter them


    # Cleanup duplicate root entry if os.walk adds it weirdly
    # This simple loop approach might be cleaner:
    output_lines = [".\n"]
    def walk_recursive(current_path: Path, level: int):
        try:
            entries = sorted(os.listdir(current_path))
        except OSError:
            return # Cannot list dir

        indent = ' ' * (4 * level)
        for entry in entries:
            entry_path = current_path / entry
            relative_entry_path = entry_path.relative_to(directory.resolve())
            relative_entry_str = str(relative_entry_path.as_posix())

            # Check ignore list first
            if any(part in ignore_list for part in relative_entry_path.parts):
                continue

            # Check gitignore
            check_path = relative_entry_str + '/' if entry_path.is_dir() else relative_entry_str
            if gitignore_specs and gitignore_specs.match_file(check_path):
                continue

            # If not ignored, add to output and recurse if dir
            output_lines.append(f"{indent}|-- {entry}\n")
            if entry_path.is_dir():
                walk_recursive(entry_path, level + 1)

    walk_recursive(directory.resolve(), 0)
    return "".join(output_lines)
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
## File: src/codesum/summary_utils.py

```py
import json
import hashlib
from pathlib import Path
import sys

from openai import OpenAI # Type hint
import pyperclip

# Import functions from other modules within the package
from . import openai_utils
from . import file_utils

SUMMARY_DIR_NAME = ".summary_files"
CODE_SUMMARY_FILENAME = "code_summary.md"
COMPRESSED_SUMMARY_FILENAME = "compressed_code_summary.md"
SELECTION_FILENAME = "previous_selection.json"
METADATA_SUFFIX = "_metadata.json"

def get_summary_dir(base_dir: Path = Path('.')) -> Path:
    """Gets the path to the summary directory within the base directory."""
    return base_dir.resolve() / SUMMARY_DIR_NAME

def create_hidden_directory(base_dir: Path = Path('.')):
    """Creates the hidden summary directory if it doesn't exist."""
    hidden_directory = get_summary_dir(base_dir)
    try:
        hidden_directory.mkdir(exist_ok=True)
    except OSError as e:
        print(f"Error creating directory {hidden_directory}: {e}", file=sys.stderr)
        # Decide if this is fatal or not, maybe return False?
        # For now, just print error and continue

def read_previous_selection(base_dir: Path = Path('.')) -> list[str]:
    """Reads previously selected file paths from JSON in the summary dir."""
    selection_file = get_summary_dir(base_dir) / SELECTION_FILENAME
    if selection_file.exists():
        try:
            with open(selection_file, "r", encoding='utf-8') as f:
                previous_selection = json.load(f)
            # Basic validation: ensure it's a list of strings (absolute paths)
            if isinstance(previous_selection, list) and all(isinstance(item, str) for item in previous_selection):
                 # Convert to absolute paths if they aren't already, though they should be stored as such
                 return [str(Path(p).resolve()) for p in previous_selection]
            else:
                 print(f"Warning: Invalid format in {selection_file}. Ignoring.", file=sys.stderr)
                 return []
        except json.JSONDecodeError:
            print(f"Warning: Could not decode {selection_file}. Ignoring.", file=sys.stderr)
            return []
        except IOError as e:
            print(f"Warning: Could not read {selection_file}: {e}. Ignoring.", file=sys.stderr)
            return []
    else:
        return []

def write_previous_selection(selected_files: list[str], base_dir: Path = Path('.')):
    """Writes the list of selected absolute file paths to JSON."""
    hidden_directory = get_summary_dir(base_dir)
    selection_file = hidden_directory / SELECTION_FILENAME
    if not hidden_directory.exists():
        # Attempt to create it if missing
        create_hidden_directory(base_dir)
        if not hidden_directory.exists(): # Check again if creation failed
             print(f"Warning: Cannot save selection, directory {hidden_directory} not found/creatable.", file=sys.stderr)
             return
    try:
        # Ensure selected_files is a list of strings (absolute paths)
        if isinstance(selected_files, list) and all(isinstance(item, str) for item in selected_files):
            # Store absolute paths for consistency
            abs_paths = [str(Path(f).resolve()) for f in selected_files]
            with open(selection_file, "w", encoding='utf-8') as f:
                json.dump(abs_paths, f, indent=4)
        else:
            print("Error: Invalid data type for selected_files. Cannot save selection.", file=sys.stderr)
    except IOError as e:
        print(f"Error writing previous selection file {selection_file}: {e}", file=sys.stderr)
    except TypeError as e:
        print(f"Error serializing selection data to JSON: {e}", file=sys.stderr)


def create_code_summary(selected_files: list[str], base_dir: Path = Path('.')):
    """Creates a basic code summary file with full content of selected files."""
    summary_directory = get_summary_dir(base_dir)
    summary_file = summary_directory / CODE_SUMMARY_FILENAME
    project_root = base_dir.resolve()

    if not summary_directory.exists():
        print(f"Warning: Summary directory {summary_directory} does not exist. Skipping summary creation.", file=sys.stderr)
        return

    try:
        gitignore_specs = file_utils.parse_gitignore(project_root)
        tree_output = file_utils.get_tree_output(project_root, gitignore_specs, file_utils.DEFAULT_IGNORE_LIST)

        with open(summary_file, "w", encoding='utf-8') as summary:
            summary.write(f"Project Root: {project_root}\n")
            summary.write(f"Project Structure:\n```\n{tree_output}\n```\n\n---\n")

            for file_path_str in selected_files: # selected_files should be absolute paths
                try:
                    file_path_obj = Path(file_path_str)
                    # Calculate relative path from project root for display
                    try:
                        relative_path = file_path_obj.relative_to(project_root)
                    except ValueError:
                        relative_path = file_path_obj # Fallback if not relative (shouldn't happen often)

                    lang_hint = file_path_obj.suffix.lstrip('.') if file_path_obj.suffix else ""

                    summary.write(f"## File: {relative_path.as_posix()}\n\n") # Use relative path for header
                    summary.write(f"```{lang_hint}\n")
                    with open(file_path_obj, "r", encoding='utf-8') as f:
                        summary.write(f.read())
                    summary.write("\n```\n---\n")
                except FileNotFoundError:
                     summary.write(f"## File: {file_path_str}\n\nError: File not found.\n\n---\n")
                except Exception as e:
                     summary.write(f"## File: {file_path_str}\n\nError reading file: {e}\n\n---\n")
    except IOError as e:
        print(f"Error writing local code summary file {summary_file}: {e}", file=sys.stderr)
    except Exception as e:
         print(f"An unexpected error occurred during local code summary creation: {e}", file=sys.stderr)


def create_compressed_summary(
    selected_files: list[str],
    client: OpenAI | None,
    llm_model: str,
    base_dir: Path = Path('.')
    ):
    """Creates a compressed summary markdown file using AI for non-main files."""
    summary_directory = get_summary_dir(base_dir)
    compressed_summary_file = summary_directory / COMPRESSED_SUMMARY_FILENAME
    project_root = base_dir.resolve()

    if not summary_directory.exists():
         print(f"Warning: Summary directory {summary_directory} does not exist. Skipping compressed summary generation.", file=sys.stderr)
         return # Or create it: create_hidden_directory()

    if not client:
        print("OpenAI client not available. Cannot generate compressed summary.", file=sys.stderr)
        # Optionally create a file indicating the error or just skip
        return

    try:
        gitignore_specs = file_utils.parse_gitignore(project_root)
        tree_output = file_utils.get_tree_output(project_root, gitignore_specs, file_utils.DEFAULT_IGNORE_LIST)

        # Overwrite existing compressed summary
        with open(compressed_summary_file, "w", encoding='utf-8') as summary:
            summary.write(f"Project Root: {project_root}\n")
            summary.write(f"Project Structure:\n```\n{tree_output}\n```\n\n---\n")

            for file_path_str in selected_files: # Absolute paths
                file_path_obj = Path(file_path_str)
                try:
                    relative_path = file_path_obj.relative_to(project_root)
                    relative_path_str = relative_path.as_posix()
                except ValueError:
                    relative_path = file_path_obj # Fallback
                    relative_path_str = str(file_path_obj)


                # Define metadata path based on relative structure *within* .summary_files
                metadata_dir_relative = relative_path.parent # Relative path of the dir
                metadata_directory = summary_directory / metadata_dir_relative
                metadata_directory.mkdir(parents=True, exist_ok=True)
                metadata_path = metadata_directory / f"{file_path_obj.name}{METADATA_SUFFIX}"

                file_summary = "" # Initialize summary variable

                # --- AI Summary Generation with Hashing ---
                try:
                    with open(file_path_obj, "r", encoding='utf-8') as f:
                        file_content = f.read()
                    current_hash = hashlib.md5(file_content.encode("utf-8")).hexdigest()
                except Exception as e:
                    print(f"Error reading file {relative_path_str} for hashing: {e}", file=sys.stderr)
                    summary.write(f"\n## File: {relative_path_str}\n\nError reading file: {e}\n---\n")
                    continue # Skip this file

                # Check cache
                use_cached = False
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r", encoding='utf-8') as metadata_file:
                            metadata = json.load(metadata_file)
                        saved_hash = metadata.get("hash")
                        if saved_hash == current_hash:
                            print(f"File '{relative_path_str}' unchanged. Using cached summary.")
                            file_summary = metadata.get("summary", "Error: Cached summary not found.")
                            use_cached = True
                        else:
                            print(f"File '{relative_path_str}' modified. Generating new summary...")
                    except json.JSONDecodeError:
                        print(f"Warning: Corrupted metadata for {relative_path_str}. Regenerating summary.", file=sys.stderr)
                    except Exception as e:
                         print(f"Error reading metadata for {relative_path_str}: {e}. Regenerating summary.", file=sys.stderr)

                # Generate summary if not cached or cache invalid/missing
                if not use_cached:
                     print(f"Generating summary for {relative_path_str}...")
                     # Call the utility function
                     file_summary = openai_utils.generate_summary(client, llm_model, file_content)
                     # Cache the new summary and hash
                     metadata = {"hash": current_hash, "summary": file_summary}
                     try:
                         with open(metadata_path, "w", encoding='utf-8') as metadata_file:
                             json.dump(metadata, metadata_file, indent=4)
                     except Exception as e:
                         print(f"Error writing metadata for {relative_path_str}: {e}", file=sys.stderr)


                # Write summary to the compressed file
                summary.write(f"\n## File: {relative_path_str}\n\nSummary:\n```markdown\n") # Assume summary is markdownish
                summary.write(file_summary)
                summary.write("\n```\n---\n")
                print(f"Processed summary for: {relative_path_str}")
                print("-----------------------------------")


    except IOError as e:
        print(f"Error writing compressed summary file {compressed_summary_file}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred during compressed summary creation: {e}", file=sys.stderr)


def copy_summary_to_clipboard(base_dir: Path = Path('.')):
    """Copies the content of the local code_summary.md to the clipboard."""
    summary_file_path = get_summary_dir(base_dir) / CODE_SUMMARY_FILENAME
    if summary_file_path.exists():
        try:
            with open(summary_file_path, "r", encoding='utf-8') as summary_file:
                summary_content = summary_file.read()
            pyperclip.copy(summary_content)
            print("Local code summary content has been copied to clipboard.")
            return True
        except pyperclip.PyperclipException as e:
            print(f"Could not copy to clipboard: {e}. You can manually copy from {summary_file_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error reading summary file for clipboard: {e}", file=sys.stderr)
    else:
        print("Local code summary file not found, skipping clipboard copy.", file=sys.stderr)
    return False
```
---
## File: src/codesum/tui.py

```py
import curses
import os
import sys
from pathlib import Path
import pathspec # For type hint

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
COLOR_PAIR_FOLDER = 1
COLOR_PAIR_STATUS = 2
COLOR_PAIR_HIGHLIGHT = 3 # For the cursor line background/foreground


# --- Main Selection Function ---
def select_files(
    directory: Path,
    previous_selection: list[str],
    gitignore_specs: pathspec.PathSpec | None,
    ignore_list: list[str]
) -> list[str]:
    """Interactively selects files using curses, hiding folders and coloring paths."""

    # Import build_tree and flatten_tree locally to avoid circular dependency potential
    # OR restructure file_utils slightly if needed. Assume they are importable.
    from . import file_utils

    tree = file_utils.build_tree(directory, gitignore_specs, ignore_list)
    # flatten_tree returns (display_name: str, full_path: str) tuples
    flattened_files = file_utils.flatten_tree(tree)

    # Convert previous_selection (absolute paths) to a set for efficient lookup
    # Ensure paths from previous selection are resolved absolute paths
    selected_paths = set(str(Path(p).resolve()) for p in previous_selection)

    # Prepare options for curses: (display_name, full_path)
    options = [(display, path) for display, path in flattened_files]

    # --- Curses Main Logic (Inner Function) ---
    def _curses_main(stdscr):
        nonlocal selected_paths # Allow modification of the set from parent scope
        curses.curs_set(0)  # Hide cursor
        current_page = 0
        current_pos = 0
        has_color = False # Determined after curses init

        # Initialize colors safely
        try:
             if curses.has_colors():
                  has_color = True
                  curses.use_default_colors() # Try for transparent background
                  # Define color pairs (adjust colors as desired)
                  curses.init_pair(COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, -1)
                  curses.init_pair(COLOR_PAIR_FOLDER, curses.COLOR_CYAN, -1)
                  curses.init_pair(COLOR_PAIR_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE) # Status bar
                  curses.init_pair(COLOR_PAIR_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_CYAN) # Highlight line
             else:
                  # Define fallback pairs for monochrome if needed, though A_REVERSE works
                  curses.init_pair(COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, curses.COLOR_BLACK)
                  curses.init_pair(COLOR_PAIR_FOLDER, curses.COLOR_WHITE, curses.COLOR_BLACK)
                  curses.init_pair(COLOR_PAIR_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
                  curses.init_pair(COLOR_PAIR_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_WHITE)
        except curses.error as e:
             # Color setup failed, proceed without color
             # print(f"Color setup error: {e}") # Debug
             has_color = False


        while True:
            h, w = stdscr.getmaxyx()
            # Ensure minimum screen size (optional)
            # if h < 5 or w < 20:
            #     stdscr.clear()
            #     stdscr.addstr(0, 0, "Terminal too small!")
            #     stdscr.refresh()
            #     key = stdscr.getch()
            #     if key == ord('q') or key == 27: break # Allow quitting
            #     continue

            page_size = max(1, h - 4) # Rows available for options

            items_on_current_page = min(page_size, len(options) - current_page * page_size)
            max_pos_on_page = items_on_current_page - 1 if items_on_current_page > 0 else 0

            # Adjust current_pos if it's out of bounds due to resize or page change
            if current_pos > max_pos_on_page:
                 current_pos = max_pos_on_page
            if current_pos < 0 : # Ensure current_pos is not negative
                 current_pos = 0

            # --- Draw Menu ---
            _draw_menu(stdscr, options, selected_paths, current_page, current_pos, page_size, has_color)

            # --- Get Key ---
            try:
                 key = stdscr.getch()
            except curses.error: # Handle interrupt during getch maybe?
                 key = -1 # Treat as no key press

            # --- Key Handling ---
            current_abs_index = current_page * page_size + current_pos
            total_options = len(options)
            total_pages = (total_options + page_size - 1) // page_size if page_size > 0 else 1

            if key == ord('q') or key == 27: # Quit
                # Optionally ask for confirmation? For now, just quit.
                # We need to return the *original* selection if user quits.
                # Let's return None to signal cancellation.
                selected_paths = None # Signal cancellation
                break
            elif key == ord(' '): # Toggle selection
                if 0 <= current_abs_index < total_options:
                    _, full_path = options[current_abs_index]
                    resolved_path = str(Path(full_path).resolve()) # Use resolved path for set
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

            elif key == curses.KEY_LEFT or key == curses.KEY_PPAGE: # Page Up
                 if current_page > 0:
                    current_page -= 1
                    current_pos = 0

            elif key == curses.KEY_RIGHT or key == curses.KEY_NPAGE: # Page Down
                 if current_page < total_pages - 1:
                    current_page += 1
                    current_pos = 0

            elif key == 10 or key == curses.KEY_ENTER:  # Confirm selection
                break # Exit loop, selected_paths holds the final set

            elif key == curses.KEY_RESIZE: # Handle terminal resize
                 # Recalculate page size and potentially current_pos
                 # The loop automatically handles redraw on next iteration
                 # Ensure current_pos remains valid is handled at top of loop
                 pass

        # Return the set of selected paths (or None if cancelled)
        return selected_paths

    # --- Draw Menu Helper (Inner Function) ---
    def _draw_menu(stdscr, options, selected_paths, current_page, current_pos, page_size, has_color):
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        # Instructions
        title = "CodeSum File Selection"
        instructions = "[SPACE] Toggle | [ENTER] Confirm | [↑↓] Navigate | [←→/PgUp/PgDn] Pages | [Q/ESC] Quit"
        try:
            stdscr.addstr(0, 0, title.ljust(w-1))
            stdscr.addstr(1, 0, instructions.ljust(w-1))
            stdscr.addstr(2, 0, "-" * (w - 1))
        except curses.error: pass # Ignore errors if window too small

        # Calculate display slice
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(options))
        current_options_page = options[start_idx:end_idx]

        # Display file list
        for idx, (display_name, full_path) in enumerate(current_options_page):
            y_pos = idx + 3 # Start below headers

            resolved_path = str(Path(full_path).resolve()) # Use resolved path for checking selection
            is_selected = resolved_path in selected_paths
            is_highlighted = idx == current_pos

            # Determine attributes
            attr = curses.A_NORMAL
            folder_attr = curses.A_NORMAL
            file_attr = curses.A_NORMAL

            if has_color:
                default_pair = curses.color_pair(COLOR_PAIR_DEFAULT)
                folder_pair = curses.color_pair(COLOR_PAIR_FOLDER)
                highlight_pair = curses.color_pair(COLOR_PAIR_HIGHLIGHT)
                attr |= default_pair
                folder_attr |= folder_pair
                file_attr |= default_pair
                if is_highlighted:
                    # Apply highlight pair to all parts of the line
                    attr = highlight_pair | curses.A_BOLD # Make highlighted bold
                    folder_attr = highlight_pair | curses.A_BOLD
                    file_attr = highlight_pair | curses.A_BOLD
            elif is_highlighted:
                 attr = curses.A_REVERSE # Fallback highlight for monochrome
                 folder_attr = curses.A_REVERSE
                 file_attr = curses.A_REVERSE


            # Render line components
            checkbox = "[X]" if is_selected else "[ ]"
            prefix = f"{checkbox} "
            max_name_width = w - len(prefix) - 1 # Max width for the display name

            # Truncate display name if necessary
            truncated_name = display_name
            if len(display_name) > max_name_width:
                 truncated_name = "..." + display_name[-(max_name_width-3):] # Show end part

            # Draw prefix
            try:
                stdscr.addstr(y_pos, 0, prefix, attr)
            except curses.error: pass

            # Draw name (with potential color split)
            x_offset = len(prefix)
            last_slash_idx = truncated_name.rfind('/')
            try:
                if has_color and last_slash_idx != -1:
                    path_part = truncated_name[:last_slash_idx + 1]
                    file_part = truncated_name[last_slash_idx + 1:]
                    stdscr.addstr(y_pos, x_offset, path_part, folder_attr)
                    # Check bounds before drawing file part
                    if x_offset + len(path_part) < w:
                         stdscr.addstr(y_pos, x_offset + len(path_part), file_part, file_attr)
                else:
                    # No color or no slash, draw whole name with base attr
                    stdscr.addstr(y_pos, x_offset, truncated_name, attr)
            except curses.error:
                # Attempt to draw truncated version if full fails near edge
                try:
                     safe_name = truncated_name[:w-x_offset-1]
                     stdscr.addstr(y_pos, x_offset, safe_name, attr)
                except curses.error: pass # Final fallback: ignore draw error

        # Status line
        total_pages = (len(options) + page_size - 1) // page_size if page_size > 0 else 1
        status = f" Page {current_page + 1}/{total_pages} | Files {start_idx + 1}-{end_idx} of {len(options)} | Selected: {len(selected_paths)} "
        status_attr = curses.color_pair(COLOR_PAIR_STATUS) if has_color else curses.A_REVERSE
        try:
            stdscr.addstr(h - 1, 0, status.ljust(w-1), status_attr)
        except curses.error: pass # Ignore error drawing status line

        stdscr.refresh()


    # --- Run Curses ---
    final_selected_paths = None # Initialize to None (meaning cancelled or error)
    try:
         selected_set = curses.wrapper(_curses_main)
         if selected_set is not None: # Check if user confirmed (didn't quit)
             # Convert set of absolute paths back to a sorted list
             final_selected_paths = sorted(list(selected_set))
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

    # Return the final selection (list of absolute paths) or None if cancelled/error
    return final_selected_paths if final_selected_paths is not None else []
```
---
## File: C:/Users/johngarfield/Documents/GitHub/codesum/pyproject.toml

```toml
## File: C:\Users\johngarfield\Documents\GitHub\codesum\pyproject.toml

Error: File not found.

---
## File: C:/Users/johngarfield/Documents/GitHub/codesum/src/codesum/app.py

```py
## File: C:\Users\johngarfield\Documents\GitHub\codesum\src\codesum\app.py

Error: File not found.

---
## File: C:/Users/johngarfield/Documents/GitHub/codesum/src/codesum/config.py

```py
## File: C:\Users\johngarfield\Documents\GitHub\codesum\src\codesum\config.py

Error: File not found.

---
## File: C:/Users/johngarfield/Documents/GitHub/codesum/src/codesum/file_utils.py

```py
## File: C:\Users\johngarfield\Documents\GitHub\codesum\src\codesum\file_utils.py

Error: File not found.

---
## File: C:/Users/johngarfield/Documents/GitHub/codesum/src/codesum/openai_utils.py

```py
## File: C:\Users\johngarfield\Documents\GitHub\codesum\src\codesum\openai_utils.py

Error: File not found.

---
## File: C:/Users/johngarfield/Documents/GitHub/codesum/src/codesum/prompts/system_readme.md

```md
## File: C:\Users\johngarfield\Documents\GitHub\codesum\src\codesum\prompts\system_readme.md

Error: File not found.

---
## File: C:/Users/johngarfield/Documents/GitHub/codesum/src/codesum/prompts/system_summary.md

```md
## File: C:\Users\johngarfield\Documents\GitHub\codesum\src\codesum\prompts\system_summary.md

Error: File not found.

---
## File: C:/Users/johngarfield/Documents/GitHub/codesum/src/codesum/summary_utils.py

```py
## File: C:\Users\johngarfield\Documents\GitHub\codesum\src\codesum\summary_utils.py

Error: File not found.

---
## File: C:/Users/johngarfield/Documents/GitHub/codesum/src/codesum/tui.py

```py
## File: C:\Users\johngarfield\Documents\GitHub\codesum\src\codesum\tui.py

Error: File not found.

---
