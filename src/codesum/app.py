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
from . import mcp_http_server

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
    parser.add_argument(
        "--mcp-server",
        action="store_true",
        help="Run the MCP server instead of the interactive application."
    )
    parser.add_argument(
        "--mcp-host",
        default="localhost",
        help="Host for the MCP server (default: localhost)"
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=8000,
        help="Port for the MCP server (default: 8000)"
    )
    # Add other arguments here if needed in the future (e.g., --non-interactive, --output-dir)
    args = parser.parse_args()

    # --- Handle Configuration Mode ---
    if args.configure:
        config.configure_settings_interactive()
        sys.exit(0) # Exit after configuration

    # --- Handle MCP Server Mode ---
    if args.mcp_server:
        mcp_http_server.run_mcp_server(args.mcp_host, args.mcp_port)
        sys.exit(0)

    # --- Normal Operation ---
    base_dir = Path('.').resolve() # Use current working directory as base
    print(f"Analyzing project root: {base_dir}")

    # 1. Load Configuration (without prompting)
    api_key, llm_model = config.load_config()

    # 2. OpenAI Client will be initialized later when needed
    openai_client = None


    # 3. Prepare Project Directory Structure & Ignores
    summary_utils.create_hidden_directory(base_dir)
    gitignore_specs = file_utils.parse_gitignore(base_dir)
    ignore_list = file_utils.DEFAULT_IGNORE_LIST # Use default ignore list
    
    # Add custom ignore patterns from .summary_files/custom_ignore.txt if it exists
    custom_ignore_file = summary_utils.get_summary_dir(base_dir) / summary_utils.CUSTOM_IGNORE_FILENAME
    if custom_ignore_file.exists():
        try:
            with open(custom_ignore_file, "r", encoding='utf-8') as f:
                custom_ignores = [line.strip() for line in f.read().splitlines() 
                                if line.strip() and not line.strip().startswith('#')]
                ignore_list.extend(custom_ignores)
        except Exception as e:
            print(f"Warning: Could not read custom ignore file {custom_ignore_file}: {e}", file=sys.stderr)

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
    # Ask if user wants to use AI features
    try:
        generate_compressed_q = input("\nGenerate AI-powered compressed summary? (y/N): ").strip().lower()
        if generate_compressed_q == 'y':
            # Initialize OpenAI client now if not already initialized
            if not openai_client:
                # Check if we have an API key, if not prompt for it
                if not api_key:
                    print("\n" + "-" * 50)
                    print("AI features require an OpenAI API Key.")
                    print(f"Configuration file: {config.CONFIG_FILE}")
                    print("-" * 50)
                    api_key_input = input("Please enter your OpenAI API Key (leave blank to skip): ").strip()
                    if api_key_input:
                        api_key = api_key_input
                        # Save the key for future use
                        config.save_config(api_key, llm_model)
                        print("API Key saved for future use.")
                    else:
                        print("No API key provided. Skipping AI features.")
                        print("\nProcess finished.")
                        return

                # Try to initialize the client
                if api_key:
                    try:
                        openai_client = OpenAI(api_key=api_key)
                        print("OpenAI client initialized.")
                    except Exception as e:
                        print(f"Error initializing OpenAI client: {e}", file=sys.stderr)
                        print("AI features disabled.")
                        print("\nProcess finished.")
                        return

            # Now proceed with compressed summary generation
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

    print("\nProcess finished.")


if __name__ == "__main__":
    # This allows running 'python -m codesum.app'
    main()