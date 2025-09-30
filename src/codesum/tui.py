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
    ignore_list: list[str],
    previous_compressed: list[str] = None
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
    # Initialize from previous compressed files
    compressed_paths = set(str(Path(p).resolve()) for p in (previous_compressed or []))

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
        if selected_paths is None:
            return None
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