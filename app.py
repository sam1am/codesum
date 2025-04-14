import os
import curses
import json
import hashlib
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import argparse
import pathspec
import pyperclip
import sys 

load_dotenv()

IGNORE_LIST = [".git", "venv", ".summary_files", "__pycache__"] # Added __pycache__ as common ignore

LLM_MODEL=os.getenv("LLM_MODEL", "gpt-4o")
print(f"Using model: {LLM_MODEL}")

# --- Helper Function to Check Terminal Color Support ---
def check_color_support():
    """Checks if the terminal likely supports colors."""
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False  # Not a tty
    # Simple check, might need refinement for specific terminals
    term = os.getenv('TERM')
    if term and 'color' in term:
        return True
    # Add more checks if needed (e.g., specific TERM values)
    return False # Default to no color if unsure

# --- Constants for Curses Colors ---
# Define color pair IDs
COLOR_PAIR_DEFAULT = 0
COLOR_PAIR_FOLDER = 1

def build_tree(directory, gitignore_specs, ignore_list):
    tree = {}
    start_dir_level = directory.count(os.sep) # Get starting depth
    for root, dirs, files in os.walk(directory, topdown=True): # topdown=True is default but explicit
        # Convert paths to relative paths for gitignore matching and display
        rel_root = os.path.relpath(root, directory)
        if rel_root == '.':
             rel_root = "" # Use empty string for root

        # Filter directories based on ignore_list and gitignore
        # We modify dirs[:] in place as required by os.walk
        dirs[:] = [d for d in dirs
                   if d not in ignore_list and
                   not any(ignore_item in os.path.join(rel_root, d) for ignore_item in ignore_list) and # Check full path part
                   not (gitignore_specs and gitignore_specs.match_file(os.path.join(rel_root, d) + '/'))]

        # Find the correct position in the tree dictionary
        current = tree
        # Handle root case correctly
        path_parts = Path(rel_root).parts
        for part in path_parts:
             # Create nested dicts only if needed
             current = current.setdefault(part, {})

        # Filter files based on gitignore
        for file in files:
            rel_path = os.path.join(rel_root, file)
            # Double check ignore list for files too
            if not any(ignore_item in rel_path for ignore_item in ignore_list):
                 if not (gitignore_specs and gitignore_specs.match_file(rel_path)):
                    # Store the full path as value
                    current[file] = os.path.join(root, file) # Use original root here

    return tree


def flatten_tree(tree, prefix=''):
    """Flattens the tree ensuring parent files come before child files."""
    items = []
    # Process files at the current level first, sorted alphabetically
    for key, value in sorted(tree.items()):
        if not isinstance(value, dict):  # It's a file
            # Ensure prefix ends with / if it's not empty
            current_prefix = prefix if not prefix or prefix.endswith('/') else prefix + '/'
            # Handle root files (prefix is empty)
            display_name = f"{current_prefix}{key}" if prefix else key
            items.append((display_name, value)) # (display name, full path)

    # Then recurse into subdirectories, sorted alphabetically
    for key, value in sorted(tree.items()):
        if isinstance(value, dict):  # It's a directory
            # Ensure prefix ends with / if it's not empty
            current_prefix = prefix if not prefix or prefix.endswith('/') else prefix + '/'
            # Handle root folders (prefix is empty)
            dir_prefix = f"{current_prefix}{key}" if prefix else key
            items.extend(flatten_tree(value, prefix=dir_prefix))
    return items


def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate code summaries and README.")
    # Keep --infer flag if needed for summary generation logic
    parser.add_argument("--infer", action="store_true", help="Enable OpenAI calls for summaries and readme (Currently not implemented in main flow)")
    return parser.parse_args()

# Check if API key exists before initializing client
if os.getenv("OPENAI_API_KEY"):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
else:
    client = None
    print("Warning: OPENAI_API_KEY not found in environment. AI features will be disabled.")


def create_hidden_directory():
    hidden_directory = Path(".summary_files")
    try:
        hidden_directory.mkdir(exist_ok=True) # exist_ok avoids error if it exists
    except OSError as e:
        print(f"Error creating directory {hidden_directory}: {e}")
        pass # Or sys.exit(1)

def get_tree_output():
    output = ""
    gitignore_specs = parse_gitignore() 

    def walk_directory_tree_recursive(directory, level, current_output=""):
        # Base ignore list check
        if any(ignore_item in Path(directory).name for ignore_item in IGNORE_LIST):
             return current_output

        try:
            entries = os.listdir(directory)
        except OSError:
            return current_output # Cannot list dir

        indent = ' ' * (4 * level)
        for entry in sorted(entries):
            entry_path = os.path.join(directory, entry)
            relative_entry_path = os.path.relpath(entry_path, ".")

            # Check ignore list first (more efficient)
            if any(ignore_item in relative_entry_path for ignore_item in IGNORE_LIST):
                continue

            # Check gitignore
            check_path = relative_entry_path + '/' if os.path.isdir(entry_path) else relative_entry_path
            if gitignore_specs and gitignore_specs.match_file(check_path):
                continue

            # If not ignored, add to output and recurse if dir
            current_output += f"{indent}|-- {entry}\n"
            if os.path.isdir(entry_path):
                current_output = walk_directory_tree_recursive(entry_path, level + 1, current_output)
        return current_output

    tree_output = ".\n" + walk_directory_tree_recursive(".", 0)
    return tree_output


def generate_summary(file_content):
    if not client:
        print("OpenAI client not initialized. Cannot generate summary.")
        return "Error: OpenAI client not available."
    print("Waiting for summary. This may take a few minutes...")
    try:
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a code documenter. Your purpose is to provide useful summaries for "
                                              "inclusion as reference for future prompts. Provide a concise summary of the "
                                              "given code and any notes that will be useful for other ChatBots to understand how it works. "
                                              "Include specific documentation about each function, class, and relevant parameters."},
                {"role": "user", "content": file_content}
            ],
            max_tokens=2500 # Consider making this configurable
        )
        summary = completion.choices[0].message.content
        return summary
    except Exception as e:
        print(f"Error calling OpenAI API for summary: {e}")
        return f"Error generating summary: {e}"


def generate_readme(compressed_summary):
    if not client:
        print("OpenAI client not initialized. Cannot generate README.")
        return "Error: OpenAI client not available."
    print("Generating updated README.md file...")
    try:
        # Using a slightly different model as originally specified, keep if intentional
        completion = client.chat.completions.create(
            model="gpt-4-1106-preview", # or LLM_MODEL
            messages=[
                {"role": "system", "content": "You are a code documenter. Your task is to create an updated README.md file for a project "
                                              "using the compressed code summary provided. Make it look nice, use emoji, and include the "
                                              "following sections: Project Description, Installation, and Usage. You can also include a "
                                              "section for Acknowledgements and a section for License."},
                {"role": "user", "content": compressed_summary}
            ],
            max_tokens=1500 # Consider making this configurable
        )
        readme_content = completion.choices[0].message.content
        return readme_content
    except Exception as e:
        print(f"Error calling OpenAI API for README: {e}")
        return f"# README Generation Error\n\nAn error occurred while generating the README:\n\n```\n{e}\n```"


def create_compressed_summary(selected_files):
    """Creates a compressed summary markdown file using AI for non-main files."""
    summary_directory = Path(".summary_files")
    compressed_summary_file = summary_directory / "compressed_code_summary.md"
    if not summary_directory.exists():
         print(f"Warning: Summary directory {summary_directory} does not exist. Skipping summary generation.")
         return # Or create it: create_hidden_directory()

    # Ensure selected_files contains full paths, not just display names
    full_selected_paths = [Path(f) for f in selected_files]

    try:
        # Overwrite existing compressed summary
        with open(compressed_summary_file, "w") as summary:
            tree_output = get_tree_output() # Get fresh tree output
            summary.write(f"Project Structure:\n```\n{tree_output}\n```\n\n---\n")

            for file_path_obj in full_selected_paths:
                relative_path_str = str(file_path_obj.relative_to(".")) # Use relative path for keys/display
                file_path_str = str(file_path_obj) # Keep full path for reading

                # Define metadata path based on relative structure
                metadata_directory = summary_directory / file_path_obj.parent.relative_to(".")
                metadata_directory.mkdir(parents=True, exist_ok=True)
                metadata_path = metadata_directory / f"{file_path_obj.name}_metadata.json"

                file_summary = "" # Initialize summary variable

                # Special handling for a specific file (e.g., main.py) - include full content
                # Adjust filename check if needed
                if file_path_obj.name == "main.py": # Example check
                    summary.write(f"\n## File: {relative_path_str}\n\nFull Content:\n```python\n") # Assume python, adjust if needed
                    try:
                        with open(file_path_str, "r", encoding='utf-8') as f:
                            file_content = f.read()
                        summary.write(file_content)
                    except Exception as e:
                        summary.write(f"\nError reading file: {e}\n")
                    summary.write("\n```\n---\n")
                    continue # Skip AI summary for this file

                # --- AI Summary Generation with Hashing ---
                try:
                    with open(file_path_str, "r", encoding='utf-8') as f:
                        file_content = f.read()
                    current_hash = hashlib.md5(file_content.encode("utf-8")).hexdigest()
                except Exception as e:
                    print(f"Error reading file {relative_path_str} for hashing: {e}")
                    summary.write(f"\n## File: {relative_path_str}\n\nError reading file: {e}\n---\n")
                    continue # Skip this file

                # Check cache
                use_cached = False
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r") as metadata_file:
                            metadata = json.load(metadata_file)
                        saved_hash = metadata.get("hash")
                        if saved_hash == current_hash:
                            print(f"File '{relative_path_str}' unchanged. Using cached summary.")
                            file_summary = metadata.get("summary", "Error: Cached summary not found.")
                            use_cached = True
                        else:
                            print(f"File '{relative_path_str}' modified. Generating new summary...")
                    except json.JSONDecodeError:
                        print(f"Warning: Corrupted metadata for {relative_path_str}. Regenerating summary.")
                    except Exception as e:
                         print(f"Error reading metadata for {relative_path_str}: {e}. Regenerating summary.")

                # Generate summary if not cached or cache invalid/missing
                if not use_cached:
                    if client: # Check if OpenAI client is available
                         print(f"Generating summary for {relative_path_str}...")
                         file_summary = generate_summary(file_content)
                         # Cache the new summary and hash
                         metadata = {"hash": current_hash, "summary": file_summary}
                         try:
                             with open(metadata_path, "w") as metadata_file:
                                 json.dump(metadata, metadata_file, indent=4)
                         except Exception as e:
                             print(f"Error writing metadata for {relative_path_str}: {e}")
                    else:
                         print(f"Skipping summary generation for {relative_path_str} (OpenAI client unavailable).")
                         file_summary = "Summary generation skipped (OpenAI client unavailable)."


                # Write summary to the compressed file
                summary.write(f"\n## File: {relative_path_str}\n\nSummary:\n```markdown\n")
                summary.write(file_summary)
                summary.write("\n```\n---\n")
                print(f"Processed summary for: {relative_path_str}")
                print("-----------------------------------")


    except IOError as e:
        print(f"Error writing compressed summary file {compressed_summary_file}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during compressed summary creation: {e}")


def parse_gitignore():
    gitignore_path = Path(".gitignore")
    gitignore_specs = None # Default to None
    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r", encoding='utf-8') as f:
                # Filter out empty lines and comments
                lines = [line for line in f.read().splitlines() if line.strip() and not line.strip().startswith('#')]
            if lines: # Only create spec if there are valid lines
                gitignore_specs = pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, lines)
        except IOError as e:
            print(f"Warning: Could not read .gitignore file: {e}")
        except Exception as e:
             print(f"Warning: Error parsing .gitignore patterns: {e}")
    return gitignore_specs

def select_files(directory, previous_selection, gitignore_specs, ignore_list):
    """Interactively selects files using curses, hiding folders and coloring paths."""
    tree = build_tree(directory, gitignore_specs, ignore_list)
    # flatten_tree now sorts correctly and only includes files
    flattened_files = flatten_tree(tree) # Contains (display_name, full_path) tuples for files only

    # Prepare options for curses: (display_name, full_path)
    # We use full_path for internal tracking and selection persistence
    options = [(display, path) for display, path in flattened_files]

    # Convert previous_selection (full paths) to a set for efficient lookup
    selected_paths = set(previous_selection)

    # Check terminal support before launching curses
    has_color = check_color_support() # Initial check

    def draw_menu(stdscr, current_page, current_pos, page_size, h, w):
        nonlocal has_color # Declare intention to modify outer scope variable here

        stdscr.clear()

        # Initialize colors if supported
        if has_color:
            try:
                curses.start_color()
                # Use default background (-1) if possible
                if curses.can_change_color() and curses.COLORS >= 16: # Check for advanced capabilities
                     curses.use_default_colors()
                     curses.init_pair(COLOR_PAIR_FOLDER, curses.COLOR_CYAN, -1)
                     curses.init_pair(COLOR_PAIR_DEFAULT, -1, -1) # Default fg/bg
                else:
                     # Basic 8 colors
                     curses.init_pair(COLOR_PAIR_FOLDER, curses.COLOR_CYAN, curses.COLOR_BLACK)
                     curses.init_pair(COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, curses.COLOR_BLACK) # Default pair

            except curses.error as e:
                # Fallback if color init fails
                # print(f"Curses color init error: {e}") # Debugging line
                has_color = False # Disable color if init fails

        # Calculate pagination
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(options))
        current_options_page = options[start_idx:end_idx]

        # Instructions
        stdscr.addstr(0, 0, "Select files: [SPACE] toggle, [ENTER] confirm, [UP/DOWN] navigate, [LEFT/RIGHT] pages.")
        stdscr.addstr(1, 0, "-" * (w - 1)) # Separator line

        # Display file list
        for idx, (display_name, full_path) in enumerate(current_options_page):
            y_pos = idx + 2 # Start below instructions

            # Determine base attribute (highlight or normal)
            base_attr = curses.A_REVERSE if idx == current_pos else curses.A_NORMAL
            # Always apply a color pair, default if color is disabled or no specific color needed
            default_color_attr = curses.color_pair(COLOR_PAIR_DEFAULT) if has_color else 0
            current_base_attr = base_attr | default_color_attr

            # Checkbox
            checkbox = "[X]" if full_path in selected_paths else "[ ]"
            # Use current_base_attr for checkbox for consistent highlighting
            try:
                stdscr.addstr(y_pos, 0, f"{checkbox} ", current_base_attr)
            except curses.error: pass # Ignore errors near edge
            x_offset = len(checkbox) + 1

            # Display name with color for path part
            last_slash_idx = display_name.rfind('/')
            try:
                # Only attempt coloring if color is enabled AND a path separator exists
                if has_color and last_slash_idx != -1:
                    path_part = display_name[:last_slash_idx + 1]
                    file_part = display_name[last_slash_idx + 1:]
                    # Combine folder color with base attribute (reverse or normal)
                    folder_attr = curses.color_pair(COLOR_PAIR_FOLDER) | (base_attr & curses.A_REVERSE)
                    # Combine default color with base attribute
                    file_attr = curses.color_pair(COLOR_PAIR_DEFAULT) | base_attr

                    stdscr.addstr(y_pos, x_offset, path_part, folder_attr)
                    # Ensure file part doesn't overwrite path part if screen is narrow
                    if x_offset + len(path_part) < w:
                         stdscr.addstr(y_pos, x_offset + len(path_part), file_part[:w - (x_offset + len(path_part)) -1], file_attr) # Truncate file_part if needed
                else:
                    # No path or no color: draw whole name with default color pair + base attribute
                    stdscr.addstr(y_pos, x_offset, display_name[:w - x_offset -1], current_base_attr) # Truncate display_name

            except curses.error:
                 # Handle potential error writing near screen edge
                 try:
                      safe_display_name = display_name[:w - x_offset - 1] # Truncate if necessary
                      stdscr.addstr(y_pos, x_offset, safe_display_name, current_base_attr)
                 except curses.error:
                      pass # Ignore if even truncated write fails


        # Status line
        total_pages = (len(options) + page_size - 1) // page_size if page_size > 0 else 1
        status = f"Page {current_page + 1}/{total_pages} | Files {start_idx + 1}-{end_idx} of {len(options)} | Selected: {len(selected_paths)}"
        try:
            stdscr.addstr(h - 1, 0, status[:w-1], curses.A_REVERSE) # Ensure status fits width
        except curses.error: pass # Ignore error drawing status line if window too small

        stdscr.refresh()

    # --- curses_main remains the same ---
    def curses_main(stdscr):
        nonlocal selected_paths # Allow modification of the set
        curses.curs_set(0)  # Hide cursor
        current_page = 0
        current_pos = 0

        while True:
            h, w = stdscr.getmaxyx()
            page_size = max(1, h - 4) # Ensure page_size is at least 1

            items_on_current_page = min(page_size, len(options) - current_page * page_size)
            max_pos_on_page = items_on_current_page - 1 if items_on_current_page > 0 else 0

            if current_pos > max_pos_on_page:
                 current_pos = max_pos_on_page

            # Call draw_menu - it will handle color setup/fallback internally
            draw_menu(stdscr, current_page, current_pos, page_size, h, w)

            key = stdscr.getch()

            # --- Key handling ---
            # Recalculate indices for key handling based on current page/pos
            current_abs_index = current_page * page_size + current_pos
            total_options = len(options)
            total_pages = (total_options + page_size - 1) // page_size if page_size > 0 else 1

            if key == ord(' ') and 0 <= current_abs_index < total_options:
                _, full_path = options[current_abs_index]
                if full_path in selected_paths:
                    selected_paths.remove(full_path)
                else:
                    selected_paths.add(full_path)
            elif key == curses.KEY_UP:
                if current_pos > 0:
                    current_pos -= 1
                elif current_page > 0: # Wrap to previous page
                    current_page -= 1
                    # Recalculate page size for the new page (might differ if last page is short)
                    h_new, w_new = stdscr.getmaxyx() # Get current dimensions
                    page_size_new = max(1, h_new - 4)
                    # Calculate items on the new (previous) page
                    items_on_prev_page = min(page_size_new, total_options - current_page * page_size_new)
                    current_pos = items_on_prev_page - 1 if items_on_prev_page > 0 else 0 # Go to last item of new page
            elif key == curses.KEY_DOWN:
                # Recalculate items on current page before checking bounds
                items_on_current_page = min(page_size, total_options - current_page * page_size)
                if current_pos < items_on_current_page - 1:
                    current_pos += 1
                elif current_page < total_pages - 1: # Wrap to next page
                    current_page += 1
                    current_pos = 0 # Go to first item of new page
            elif key == curses.KEY_LEFT:
                 if current_page > 0:
                    current_page -= 1
                    current_pos = 0 # Go to first item of new page
            elif key == curses.KEY_RIGHT:
                 if current_page < total_pages - 1:
                    current_page += 1
                    current_pos = 0 # Go to first item of new page
            elif key == 10 or key == curses.KEY_ENTER:  # Enter key
                break # Exit loop
            elif key == curses.KEY_RESIZE: # Handle terminal resize
                 h_new, w_new = stdscr.getmaxyx()
                 page_size_new = max(1, h_new - 4)
                 items_on_current_page_new = min(page_size_new, total_options - current_page * page_size_new)
                 max_pos_new = items_on_current_page_new - 1 if items_on_current_page_new > 0 else 0
                 if current_pos > max_pos_new:
                      current_pos = max_pos_new
                 # Screen will be redrawn by draw_menu at start of next loop iteration
            elif key == ord('q') or key == 27: # Add 'q' or ESC to quit
                 break

    # Run the curses application
    try:
         curses.wrapper(curses_main)
    except curses.error as e:
         print(f"\nCurses error occurred: {e}")
         print("Window might be too small or terminal incompatible.")
         # Fallback or exit cleanly
         print("Returning currently selected files (if any).")

    # Return the final selection as a list of full paths, sorted for consistency
    return sorted(list(selected_paths))


def create_code_summary(selected_files):
    """Creates a basic code summary file with full content of selected files."""
    summary_directory = Path(".summary_files")
    summary_file = summary_directory / "code_summary.md"
    if not summary_directory.exists():
         print(f"Warning: Summary directory {summary_directory} does not exist. Skipping summary creation.")
         return

    try:
        with open(summary_file, "w", encoding='utf-8') as summary:
            tree_output = get_tree_output() # Get fresh tree output
            summary.write(f"Project Structure:\n```\n{tree_output}\n```\n\n---\n")

            for file_path_str in selected_files: # selected_files should be full paths
                try:
                    file_path_obj = Path(file_path_str)
                    relative_path = file_path_obj.relative_to(".")
                    # Determine language hint for markdown block (basic example)
                    lang_hint = file_path_obj.suffix.lstrip('.') if file_path_obj.suffix else ""

                    summary.write(f"## File: {relative_path}\n\n") # Use relative path for header
                    summary.write(f"```{lang_hint}\n")
                    with open(file_path_obj, "r", encoding='utf-8') as f:
                        summary.write(f.read())
                    summary.write("\n```\n---\n")
                except FileNotFoundError:
                     summary.write(f"## File: {file_path_str}\n\nError: File not found.\n\n---\n")
                except Exception as e:
                     summary.write(f"## File: {file_path_str}\n\nError reading file: {e}\n\n---\n")
    except IOError as e:
        print(f"Error writing local code summary file {summary_file}: {e}")


def read_previous_selection():
    """Reads previously selected file paths from JSON."""
    hidden_directory = Path(".summary_files")
    selection_file = hidden_directory / "previous_selection.json"
    if selection_file.exists():
        try:
            with open(selection_file, "r", encoding='utf-8') as f:
                previous_selection = json.load(f)
                # Basic validation: ensure it's a list of strings
                if isinstance(previous_selection, list) and all(isinstance(item, str) for item in previous_selection):
                     return previous_selection
                else:
                     print("Warning: Invalid format in previous_selection.json. Ignoring.")
                     return []
        except json.JSONDecodeError:
            print("Warning: Could not decode previous_selection.json. Ignoring.")
            return []
        except IOError as e:
            print(f"Warning: Could not read previous_selection.json: {e}. Ignoring.")
            return []
    else:
        return [] # No previous selection found

def write_previous_selection(selected_files):
    """Writes the list of selected file paths to JSON."""
    hidden_directory = Path(".summary_files")
    selection_file = hidden_directory / "previous_selection.json"
    if not hidden_directory.exists():
        print(f"Warning: Cannot save selection, directory {hidden_directory} not found.")
        return
    try:
        with open(selection_file, "w", encoding='utf-8') as f:
            # Ensure selected_files is a list of strings (full paths)
            if isinstance(selected_files, list) and all(isinstance(item, str) for item in selected_files):
                json.dump(selected_files, f, indent=4)
            else:
                print("Error: Invalid data type for selected_files. Cannot save selection.")
    except IOError as e:
        print(f"Error writing previous selection file {selection_file}: {e}")
    except TypeError as e:
        print(f"Error serializing selection data to JSON: {e}")


def main():
    # args = parse_arguments() # Parse args if needed (e.g., for --infer)
    create_hidden_directory()

    gitignore_specs = parse_gitignore()
    # Ensure IGNORE_LIST contains common temporary/generated dirs
    ignore_list = IGNORE_LIST # Use the global list

    previous_selection = read_previous_selection()
    print("Loading file selection interface...")

    # Pass directory '.' to start from current dir
    selected_files = select_files(".", previous_selection, gitignore_specs, ignore_list)

    if not selected_files:
        print("No files selected. Exiting.")
        return

    print("\nSelected files:")
    for f in selected_files:
        # Display relative path for clarity
        try:
             print(f"- {Path(f).relative_to('.')}")
        except ValueError:
             print(f"- {f}") # Fallback if not relative to '.'

    # Save the current selection (list of full paths)
    write_previous_selection(selected_files)
    print(f"\nSelection saved to '.summary_files/previous_selection.json'.")

    # Create the local code summary (full content)
    create_code_summary(selected_files)
    print("Local code summary (full content) created in '.summary_files/code_summary.md'.")

    # Copy code_summary.md contents to clipboard
    summary_file_path = Path(".summary_files") / "code_summary.md"
    if summary_file_path.exists():
        try:
            with open(summary_file_path, "r", encoding='utf-8') as summary_file:
                summary_content = summary_file.read()
            pyperclip.copy(summary_content)
            print("Local code summary content has been copied to clipboard.")
        except pyperclip.PyperclipException as e:
            print(f"Could not copy to clipboard: {e}. You can manually copy from {summary_file_path}")
        except Exception as e:
            print(f"Error reading summary file for clipboard: {e}")
    else:
        print("Local code summary file not found, skipping clipboard copy.")


    # --- Optional AI Features ---
    if client: # Only ask if OpenAI client is available
        try:
            # Ask user if they want to generate a compressed summary (using AI)
            generate_compressed_q = input("\nGenerate AI-powered compressed summary? (y/N): ").strip().lower()
            if generate_compressed_q == 'y':
                create_compressed_summary(selected_files) # This now uses AI
                print("\nAI-powered compressed code summary created in '.summary_files/compressed_code_summary.md'.")

                # Ask user if they want to generate an updated README (only if compressed summary was created)
                compressed_summary_file = Path(".summary_files") / "compressed_code_summary.md"
                if compressed_summary_file.exists():
                    generate_readme_q = input("Generate updated README.md using AI summary? (y/N): ").strip().lower()
                    if generate_readme_q == 'y':
                        try:
                            with open(compressed_summary_file, "r", encoding='utf-8') as f:
                                compressed_summary_content = f.read()

                            if compressed_summary_content.strip(): # Ensure content exists
                                readme_content = generate_readme(compressed_summary_content)
                                readme_file = Path("README.md")
                                with open(readme_file, "w", encoding='utf-8') as f:
                                    f.write(readme_content)
                                print("\nUpdated README.md file generated successfully.")
                            else:
                                print("Compressed summary is empty. Skipping README generation.")

                        except FileNotFoundError:
                            print("Error: Compressed summary file not found. Cannot generate README.")
                        except Exception as e:
                            print(f"Error during README generation: {e}")
                else:
                    print("Compressed summary file not found. Skipping README generation prompt.")

        except EOFError:
             print("\nInput interrupted. Exiting AI feature prompts.")
    else:
        print("\nOpenAI API key not configured. Skipping AI summary and README generation.")

    print("\nProcess finished.")


if __name__ == "__main__":
    # Check if OPENAI_API_KEY is set before running main potentially
    # if not os.getenv("OPENAI_API_KEY"):
    #     print("Warning: OPENAI_API_KEY environment variable is not set.")
    #     # decide whether to exit or continue without AI features
    main()