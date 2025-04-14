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