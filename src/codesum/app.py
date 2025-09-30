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
    previous_selection, previous_compressed = summary_utils.read_previous_selection(base_dir) # Returns (selected_files, compressed_files)

    # 5. Run Interactive File Selection
    print("Loading file selection interface...")
    # select_files expects absolute paths in previous_selection and previous_compressed, returns tuple of (selected_files, compressed_files)
    selected_files, compressed_files = tui.select_files(base_dir, previous_selection, gitignore_specs, ignore_list, previous_compressed)

    if not selected_files:
        # Check if selection was cancelled (tui returns empty list now) or genuinely empty
        print("No files selected or selection cancelled. Exiting.")
        return

    # 6. Save Current Selection (absolute paths) including compressed files
    summary_utils.write_previous_selection(selected_files, base_dir, compressed_files)

    # 7. Create Local Code Summary (Full Content, with compressed summaries for marked files)
    # Initialize OpenAI client if needed for compressed summaries
    if compressed_files and not openai_client:
        if not api_key:
            print("\n" + "-" * 50)
            print("Compressed summaries require an OpenAI API Key.")
            print(f"Configuration file: {config.CONFIG_FILE}")
            print("-" * 50)
            api_key_input = input("Please enter your OpenAI API Key (leave blank to skip compressed summaries): ").strip()
            if api_key_input:
                api_key = api_key_input
                # Save the key for future use
                config.save_config(api_key, llm_model)
                print("API Key saved for future use.")
            else:
                print("No API key provided. Skipping compressed summaries for marked files.")
                compressed_files = []

        # Try to initialize the client if we have an API key
        if api_key and compressed_files:
            try:
                openai_client = OpenAI(api_key=api_key)
                print("OpenAI client initialized for compressed summaries.")
            except Exception as e:
                print(f"Error initializing OpenAI client: {e}", file=sys.stderr)
                print("Compressed summaries will be skipped.")
                compressed_files = []

    print("\n\033[36m⚙ Generating code summary...\033[0m")
    summary_utils.create_code_summary(selected_files, base_dir, compressed_files, openai_client, llm_model)
    local_summary_path = summary_utils.get_summary_dir(base_dir) / summary_utils.CODE_SUMMARY_FILENAME

    # Count tokens
    token_count = 0
    if local_summary_path.exists():
        try:
            with open(local_summary_path, "r", encoding='utf-8') as f:
                content = f.read()
            token_count = openai_utils.count_tokens(content)
        except Exception as e:
            print(f"\033[33m⚠ Error counting tokens: {e}\033[0m", file=sys.stderr)

    # 8. Copy to Clipboard automatically
    summary_utils.copy_summary_to_clipboard(base_dir)

    # Print cool ASCII art logo with stats
    # Box width is 75 chars (including ║ on each side)
    BOX_WIDTH = 75
    CONTENT_WIDTH = BOX_WIDTH - 4  # Subtract 4 for "║  " and "  ║"

    print("\n\033[36m")
    print("╔═════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                         ║")
    print("║   ██████╗ ██████╗ ██████╗ ███████╗███████╗██╗   ██╗███╗   ███╗          ║")
    print("║  ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔════╝██║   ██║████╗ ████║          ║")
    print("║  ██║     ██║   ██║██║  ██║█████╗  ███████╗██║   ██║██╔████╔██║          ║")
    print("║  ██║     ██║   ██║██║  ██║██╔══╝  ╚════██║██║   ██║██║╚██╔╝██║          ║")
    print("║  ╚██████╗╚██████╔╝██████╔╝███████╗███████║╚██████╔╝██║ ╚═╝ ██║          ║")
    print("║   ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝          ║")
    print("║                                                                         ║")

    # Success message line
    success_msg = "✓ Code summary copied to clipboard!"
    padding = " " * (CONTENT_WIDTH - len(success_msg))
    print(f"║  \033[0m\033[32m{success_msg}\033[0m\033[36m{padding}║")
    print("║                                                                         ║")
    print("╠═════════════════════════════════════════════════════════════════════════╣")

    # Stats section
    files_line = f"Selected Files: {len(selected_files)}"
    padding = " " * (CONTENT_WIDTH - len(files_line))
    print(f"║  \033[0m\033[1m{files_line}\033[0m\033[36m{padding}║")

    if compressed_files:
        comp_line = f"Compressed Summaries: {len(compressed_files)}"
        padding = " " * (CONTENT_WIDTH - len(comp_line))
        print(f"║  \033[0m\033[1m{comp_line}\033[0m\033[36m{padding}║")

    token_str = f"{token_count:,}" if token_count > 0 else "0"
    tokens_line = f"Total Tokens: {token_str}"
    padding = " " * (CONTENT_WIDTH - len(tokens_line))
    print(f"║  \033[0m\033[1m{tokens_line}\033[0m\033[36m{padding}║")
    print("║                                                                         ║")

    # Show all files
    files_header = "Files:"
    padding = " " * (CONTENT_WIDTH - len(files_header))
    print(f"║  \033[0m\033[1m{files_header}\033[0m\033[36m{padding}║")

    for f_abs_str in selected_files:
        f_path = Path(f_abs_str)
        try:
            rel_path = f_path.relative_to(base_dir).as_posix()
        except ValueError:
            rel_path = f_path.name

        # Truncate if too long (max 67 chars for path + marker and space)
        if len(rel_path) > 67:
            rel_path = "..." + rel_path[-64:]

        # Mark compressed files with star
        marker = "★" if f_abs_str in compressed_files else "•"
        file_line = f"{marker} {rel_path}"
        padding = " " * (CONTENT_WIDTH - len(file_line))
        print(f"║  \033[0m{file_line}\033[36m{padding}║")

    print("║                                                                         ║")
    print("╚═════════════════════════════════════════════════════════════════════════╝")
    print("\033[0m")


if __name__ == "__main__":
    # This allows running 'python -m codesum.app'
    main()