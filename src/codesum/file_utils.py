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
    Determine if a file is a text file by analyzing content first, with smart fallbacks.
    """
    # Quick wins: definitely text extensions (minimal list)
    definitely_text = {'.txt', '.md', '.json',
                       '.xml', '.csv', '.log', '.ini', '.cfg'}
    if file_path.suffix.lower() in definitely_text:
        return True

    # Quick losses: definitely binary extensions
    definitely_binary = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.webp',
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv',
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',
        '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
        '.exe', '.dll', '.so', '.dylib', '.app',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
    }
    if file_path.suffix.lower() in definitely_binary:
        return False

    # For everything else (including .ts files), analyze the content
    return _analyze_file_content(file_path)


def _analyze_file_content(file_path: Path, sample_size: int = 8192) -> bool:
    """
    Analyze file content to determine if it's likely a text file.
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(sample_size)

        if not chunk:  # Empty file
            return True

        # Check for null bytes (strong indicator of binary)
        if b'\x00' in chunk:
            return False

        # Check for too many control characters (except common ones like \t, \n, \r)
        control_chars = sum(1 for byte in chunk if byte <
                            32 and byte not in (9, 10, 13))
        if control_chars > len(chunk) * 0.1:  # More than 10% control chars
            return False

        # Try to decode as UTF-8
        try:
            text = chunk.decode('utf-8')

            # Additional heuristics for text files:
            # Check for reasonable printable character ratio
            printable_chars = sum(
                1 for char in text if char.isprintable() or char.isspace())
            printable_ratio = printable_chars / len(text) if text else 1

            return printable_ratio > 0.7  # At least 70% printable characters

        except UnicodeDecodeError:
            # Try other common encodings
            for encoding in ['latin-1', 'ascii', 'utf-16']:
                try:
                    chunk.decode(encoding)
                    return True  # Successfully decoded with some encoding
                except UnicodeDecodeError:
                    continue

            return False  # Couldn't decode with any common encoding

    except (IOError, OSError):
        return False  # Can't read file, assume binary


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


def build_tree_with_folders(directory: Path, gitignore_specs: pathspec.PathSpec | None, ignore_list: list[str]):
    """Builds a nested dictionary representing the directory structure, including folders."""
    tree = {}
    # Use resolved absolute path for reliable comparison
    base_dir_path = Path(directory).resolve()

    # First, add all directories (even empty ones)
    for dir_path in base_dir_path.rglob('*'):
        if dir_path.is_dir():
            try:
                # Get path relative to the starting directory
                relative_path = dir_path.relative_to(base_dir_path)
                # Use posix for consistent matching
                relative_path_str = str(relative_path.as_posix())

                # 1. Check explicit ignore_list (faster check)
                if any(part in ignore_list for part in relative_path.parts):
                    continue
                # Check if any parent dir is in ignore list
                if any(ignore_item in parent.name for parent in relative_path.parents for ignore_item in ignore_list if parent != Path('.')):
                    continue

                # 2. Check combined .gitignore patterns
                check_path = relative_path_str + '/'
                if gitignore_specs and gitignore_specs.match_file(check_path):
                    continue

                # If not ignored, add to tree
                current_level = tree
                parts = relative_path.parts

                for part in parts:
                    current_level = current_level.setdefault(part, {})

            except PermissionError:
                continue  # Skip dirs we can't access
            except Exception as e:
                print(
                    f"Warning: Error processing directory path {dir_path}: {e}", file=sys.stderr)
                continue

    # Then, add files to the tree
    for item_path in base_dir_path.rglob('*'):
        try:
            # Get path relative to the starting directory
            relative_path = item_path.relative_to(base_dir_path)
            # Use posix for consistent matching
            relative_path_str = str(relative_path.as_posix())

            # 1. Check explicit ignore_list (faster check)
            if any(part in ignore_list for part in relative_path.parts):
                continue
            # Check if any parent dir is in ignore list
            if any(ignore_item in parent.name for parent in relative_path.parents for ignore_item in ignore_list if parent != Path('.')):
                continue

            # 2. Check combined .gitignore patterns
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
                        # Ensure directory entry exists
                        current_level = current_level.setdefault(part, {})
                else:  # Intermediate directory part
                    current_level = current_level.setdefault(part, {})

        except PermissionError:
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


def flatten_tree_with_folders(tree, prefix='', folder_paths=None, expanded_folders=None):
    """
    Flattens the tree for display, including folders.
    Returns list of tuples: (display_name, path, is_folder, full_path_if_file)
    """
    if folder_paths is None:
        folder_paths = {}
    if expanded_folders is None:
        expanded_folders = set()
        
    items = []
    # Process files and folders at the current level, sorted alphabetically
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
        items.append((display_name, f"{prefix}{key}", False, full_path))  # (display name, path, is_folder, full_path)

    # Add sorted folders
    for key, sub_tree in sorted(dirs_at_level.items()):
        folder_path = f"{prefix}{key}"
        display_name = f"{prefix}{key}/"
        is_expanded = folder_path in expanded_folders
        items.append((display_name, folder_path, True, None))  # (display name, path, is_folder, full_path)
        
        # If folder is expanded, recurse into it
        if is_expanded:
            items.extend(flatten_tree_with_folders(sub_tree, prefix=f"{prefix}{key}/", 
                                                 folder_paths=folder_paths, 
                                                 expanded_folders=expanded_folders))

    return items


def flatten_tree_with_folders_collapsed(tree, prefix='', folder_paths=None, collapsed_folders=None):
    """
    Flattens the tree for display, including folders, with collapsed state tracking.
    For folders that contain only one file, skips the folder and shows only the file.
    Returns list of tuples: (display_name, path, is_folder, full_path_if_file)
    """
    if folder_paths is None:
        folder_paths = {}
    if collapsed_folders is None:
        collapsed_folders = set()
        
    items = []
    # Process files and folders at the current level, sorted alphabetically
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
        items.append((display_name, f"{prefix}{key}", False, full_path))  # (display name, path, is_folder, full_path)

    # Add sorted folders
    for key, sub_tree in sorted(dirs_at_level.items()):
        folder_path = f"{prefix}{key}"
        
        # Check if this folder contains only one file and no subdirectories
        if _folder_has_single_file(sub_tree):
            # Skip the folder and show only the file with the folder path as prefix
            for sub_key, sub_value in sub_tree.items():
                if not isinstance(sub_value, dict):  # This is the single file
                    display_name = f"{prefix}{key}/{sub_key}"
                    items.append((display_name, f"{prefix}{key}/{sub_key}", False, sub_value))  # Show as file, not folder
                    break
        else:
            # Show folder normally
            display_name = f"{prefix}{key}/"
            is_collapsed = folder_path in collapsed_folders
            items.append((display_name, folder_path, True, None))  # (display name, path, is_folder, full_path)
            
            # If folder is NOT collapsed, recurse into it
            if not is_collapsed:
                items.extend(flatten_tree_with_folders_collapsed(sub_tree, prefix=f"{prefix}{key}/", 
                                                     folder_paths=folder_paths, 
                                                     collapsed_folders=collapsed_folders))

    return items


def _folder_has_single_file(folder_tree: dict) -> bool:
    """
    Check if a folder contains only one file and no subdirectories.
    """
    file_count = 0
    dir_count = 0
    
    for key, value in folder_tree.items():
        if isinstance(value, dict):
            # This is a subdirectory
            dir_count += 1
        else:
            # This is a file
            file_count += 1
    
    # Return True only if there's exactly one file and no subdirectories
    return file_count == 1 and dir_count == 0


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
