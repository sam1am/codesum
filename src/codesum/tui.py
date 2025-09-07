import curses
import os
import sys
from pathlib import Path
import pathspec # For type hint

# Import our new folder_utils
from . import folder_utils

# --- Helper Functions ---
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
COLOR_PAIR_FOLDER_ITEM = 2  # Orange for folder items in the list
COLOR_PAIR_FILE = 3
COLOR_PAIR_STATUS = 4 # For the cursor line background/foreground
COLOR_PAIR_HIGHLIGHT = 5 # For the cursor line background/foreground


# --- Main Selection Function ---
def select_files(
    directory: Path,
    previous_selection: list[str],
    gitignore_specs: pathspec.PathSpec | None,
    ignore_list: list[str]
) -> list[str]:
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

    # Prepare options for curses: (display_name, path, is_folder, full_path)
    options = [(display, path, is_folder, full_path) for display, path, is_folder, full_path in flattened_items]
    
    # Store the directory path for display in the header
    directory_path = str(directory.resolve())
    
    # Store reference to tree for folder operations
    tree_ref = tree

    # --- Curses Main Logic (Inner Function) ---
    def _curses_main(stdscr):
        nonlocal selected_paths, collapsed_folders # Allow modification of the set from parent scope
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
                  curses.init_pair(COLOR_PAIR_FOLDER_PATH, curses.COLOR_BLUE, -1)  # Blue for folder paths
                  curses.init_pair(COLOR_PAIR_FOLDER_ITEM, curses.COLOR_GREEN, -1)  # Green for folder items
                  curses.init_pair(COLOR_PAIR_FILE, curses.COLOR_WHITE, -1)
                  curses.init_pair(COLOR_PAIR_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE) # Status bar
                  curses.init_pair(COLOR_PAIR_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_CYAN) # Highlight line
             else:
                  # Define fallback pairs for monochrome if needed, though A_REVERSE works
                  curses.init_pair(COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, curses.COLOR_BLACK)
                  curses.init_pair(COLOR_PAIR_FOLDER_PATH, curses.COLOR_WHITE, curses.COLOR_BLACK)
                  curses.init_pair(COLOR_PAIR_FOLDER_ITEM, curses.COLOR_WHITE, curses.COLOR_BLACK)
                  curses.init_pair(COLOR_PAIR_FILE, curses.COLOR_WHITE, curses.COLOR_BLACK)
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
            _draw_menu(stdscr, options, selected_paths, collapsed_folders, current_page, current_pos, page_size, has_color, directory_path)

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
                # Save collapsed folder states before quitting
                summary_utils.write_previous_collapsed_folders(list(collapsed_folders), directory)
                # Optionally ask for confirmation? For now, just quit.
                # We need to return the *original* selection if user quits.
                # Let's return None to signal cancellation.
                selected_paths = None # Signal cancellation
                break
            elif key == ord('a') or key == ord('A'):  # Select/Deselect all
                # Get all file paths from options
                all_file_paths = set(str(Path(full_path).resolve()) for _, _, is_folder, full_path in options if not is_folder and full_path)
                # If all files are already selected, deselect all
                if selected_paths == all_file_paths:
                    selected_paths.clear()
                else:
                    # Otherwise, select all (only applicable when not in single file mode)
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

            elif key == ord('f') or key == ord('F'):  # Toggle folder selection
                if 0 <= current_abs_index < total_options:
                    display_name, path, is_folder, full_path = options[current_abs_index]
                    if is_folder:
                        # Get all files in this folder
                        folder_files = folder_utils.collect_files_in_folder(path, tree_ref)
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
                # Save collapsed folder states before confirming
                summary_utils.write_previous_collapsed_folders(list(collapsed_folders), directory)
                break # Exit loop, selected_paths holds the final set

            elif key == curses.KEY_RESIZE: # Handle terminal resize
                 # Recalculate page size and potentially current_pos
                 # The loop automatically handles redraw on next iteration
                 # Ensure current_pos remains valid is handled at top of loop
                 pass

        # Return the set of selected paths (or None if cancelled)
        return selected_paths

    # --- Draw Menu Helper (Inner Function) ---
    def _draw_menu(stdscr, options, selected_paths, collapsed_folders, current_page, current_pos, page_size, has_color, directory_path):
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        # Instructions
        title = f"CodeSum File Selection - {directory_path}"
        instructions = "[SPACE] Toggle/File Collapse | [F] Select/Deselect Folder | [A] Select/Deselect All Files | [ENTER] Confirm | [↑↓] Navigate | [←→/PgUp/PgDn] Pages | [Q/ESC] Quit"
        try:
            stdscr.addstr(0, 0, title.ljust(w-1))
            stdscr.addstr(1, 0, instructions.ljust(w-1))
            stdscr.addstr(2, 0, "-" * (w - 1))
        except curses.error: pass # Ignore errors if window too small

        # Calculate display slice
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(options))
        current_options_page = options[start_idx:end_idx]

        # Display file/folder list
        for idx, (display_name, path, is_folder, full_path) in enumerate(current_options_page):
            y_pos = idx + 3 # Start below headers

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
                checkbox = f"{indicator} "
            else:
                # Show file with regular checkbox
                checkbox = "[X] " if is_selected else "[ ] "
                
            prefix = f"{checkbox}"
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
            except curses.error:
                # Attempt to draw truncated version if full fails near edge
                try:
                     safe_name = truncated_name[:w-x_offset-1]
                     stdscr.addstr(y_pos, x_offset, safe_name, attr)
                except curses.error: pass # Final fallback: ignore draw error


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