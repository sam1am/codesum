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