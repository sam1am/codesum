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
    Determine if a file is a text file based on its MIME type or by reading a small portion.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        bool: True if the file is likely a text file, False otherwise
    """
    # First check the MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        # Text files typically have MIME types starting with 'text/'
        if mime_type.startswith('text/'):
            return True
        # Explicitly exclude common binary types
        if mime_type.startswith(('image/', 'audio/', 'video/')) or mime_type in [
            'application/octet-stream', 'application/pdf', 'application/zip',
            'application/x-tar', 'application/gzip', 'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]:
            return False
    
    # If MIME type is not helpful, try to read a small portion of the file
    try:
        # Try to read the first 1024 bytes
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
        
        # Check if the chunk contains null bytes (common in binary files)
        if b'\x00' in chunk:
            return False
            
        # Try to decode as UTF-8
        chunk.decode('utf-8')
        return True
    except (UnicodeDecodeError, IOError):
        return False


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
