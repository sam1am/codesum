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