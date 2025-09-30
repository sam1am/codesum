import json
import hashlib
from pathlib import Path
import sys

from openai import OpenAI # Type hint
import pyperclip

# Import functions from other modules within the package
from . import openai_utils
from . import file_utils

SUMMARY_DIR_NAME = ".summary_files"
CUSTOM_IGNORE_FILENAME = "codesum_ignore.txt"
CODE_SUMMARY_FILENAME = "code_summary.md"
COMPRESSED_SUMMARY_FILENAME = "compressed_code_summary.md"
SELECTION_FILENAME = "previous_selection.json"
COLLAPSED_FOLDERS_FILENAME = "collapsed_folders.json"
METADATA_SUFFIX = "_metadata.json"
SELECTION_CONFIGS_FILENAME = "selection_configs.json"

def get_summary_dir(base_dir: Path = Path('.')) -> Path:
    """Gets the path to the summary directory within the base directory."""
    return base_dir.resolve() / SUMMARY_DIR_NAME

def create_hidden_directory(base_dir: Path = Path('.')):
    """Creates the hidden summary directory if it doesn't exist and creates a custom ignore file."""
    hidden_directory = get_summary_dir(base_dir)
    try:
        hidden_directory.mkdir(exist_ok=True)
        
        # Create custom ignore file if it doesn't exist
        custom_ignore_file = hidden_directory / CUSTOM_IGNORE_FILENAME
        if not custom_ignore_file.exists():
            with open(custom_ignore_file, "w", encoding='utf-8') as f:
                f.write("# Add custom ignore patterns here, one per line\n")
                f.write("# These patterns will be added to the default ignores and .gitignore patterns\n")
                f.write("# Example:\n")
                f.write("# *.log\n")
                f.write("# temp/\n")
                f.write("# secret.txt\n")
    except OSError as e:
        print(f"Error creating directory {hidden_directory}: {e}", file=sys.stderr)
        # Decide if this is fatal or not, maybe return False?
        # For now, just print error and continue


def read_previous_selection(base_dir: Path = Path('.')) -> tuple[list[str], list[str]]:
    """Reads previously selected file paths and compressed file paths from JSON in the summary dir.
    Automatically removes files that no longer exist and updates the stored selection.
    Returns tuple of (selected_files, compressed_files)."""
    selection_file = get_summary_dir(base_dir) / SELECTION_FILENAME
    if selection_file.exists():
        try:
            with open(selection_file, "r", encoding='utf-8') as f:
                data = json.load(f)

            # Support both old format (list) and new format (dict)
            if isinstance(data, list):
                # Old format: just a list of selected files
                previous_selection = data
                previous_compressed = []
            elif isinstance(data, dict):
                # New format: dict with selected_files and compressed_files
                previous_selection = data.get("selected_files", [])
                previous_compressed = data.get("compressed_files", [])
            else:
                print(
                    f"Warning: Invalid format in {selection_file}. Ignoring.", file=sys.stderr)
                return ([], [])

            # Basic validation: ensure they're lists of strings (absolute paths)
            if not (isinstance(previous_selection, list) and all(isinstance(item, str) for item in previous_selection)):
                print(
                    f"Warning: Invalid selected_files format in {selection_file}. Ignoring.", file=sys.stderr)
                return ([], [])

            if not (isinstance(previous_compressed, list) and all(isinstance(item, str) for item in previous_compressed)):
                print(
                    f"Warning: Invalid compressed_files format in {selection_file}. Ignoring.", file=sys.stderr)
                previous_compressed = []

            # Convert to absolute paths if they aren't already
            abs_paths = [str(Path(p).resolve()) for p in previous_selection]
            abs_compressed = [str(Path(p).resolve()) for p in previous_compressed]

            # Filter out files that no longer exist
            existing_paths = []
            existing_compressed = []
            removed_count = 0

            for path in abs_paths:
                if Path(path).exists():
                    existing_paths.append(path)
                else:
                    removed_count += 1
                    print(
                        f"Warning: Previously selected file no longer exists and will be removed: {path}", file=sys.stderr)

            # Also clean up compressed list - only keep files that exist and are still selected
            for path in abs_compressed:
                if Path(path).exists() and path in existing_paths:
                    existing_compressed.append(path)
                elif not Path(path).exists():
                    removed_count += 1

            # If any files were removed, update the stored selection
            if removed_count > 0:
                print(
                    f"Removed {removed_count} non-existent file(s) from previous selection.", file=sys.stderr)
                try:
                    # Write back the cleaned selection
                    write_previous_selection(existing_paths, base_dir, existing_compressed)
                except Exception as e:
                    print(
                        f"Warning: Could not update previous selection file after cleanup: {e}", file=sys.stderr)

            return (existing_paths, existing_compressed)

        except json.JSONDecodeError:
            print(
                f"Warning: Could not decode {selection_file}. Ignoring.", file=sys.stderr)
            return ([], [])
        except IOError as e:
            print(
                f"Warning: Could not read {selection_file}: {e}. Ignoring.", file=sys.stderr)
            return ([], [])
    else:
        return ([], [])

def write_previous_selection(selected_files: list[str], base_dir: Path = Path('.'), compressed_files: list[str] = None):
    """Writes the list of selected absolute file paths and compressed file paths to JSON."""
    hidden_directory = get_summary_dir(base_dir)
    selection_file = hidden_directory / SELECTION_FILENAME
    if not hidden_directory.exists():
        # Attempt to create it if missing
        create_hidden_directory(base_dir)
        if not hidden_directory.exists(): # Check again if creation failed
             print(f"Warning: Cannot save selection, directory {hidden_directory} not found/creatable.", file=sys.stderr)
             return
    try:
        # Ensure selected_files is a list of strings (absolute paths)
        if isinstance(selected_files, list) and all(isinstance(item, str) for item in selected_files):
            # Store absolute paths for consistency
            abs_paths = [str(Path(f).resolve()) for f in selected_files]
            abs_compressed = [str(Path(f).resolve()) for f in (compressed_files or [])]

            # Save in new format with both selected and compressed
            data = {
                "selected_files": abs_paths,
                "compressed_files": abs_compressed
            }
            with open(selection_file, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        else:
            print("Error: Invalid data type for selected_files. Cannot save selection.", file=sys.stderr)
    except IOError as e:
        print(f"Error writing previous selection file {selection_file}: {e}", file=sys.stderr)
    except TypeError as e:
        print(f"Error serializing selection data to JSON: {e}", file=sys.stderr)


def create_code_summary(
    selected_files: list[str],
    base_dir: Path = Path('.'),
    compressed_files: list[str] = None,
    client: OpenAI | None = None,
    llm_model: str = None
):
    """Creates a basic code summary file with full content of selected files.

    For files in compressed_files list, generates AI-powered compressed summaries instead of full content.
    """
    summary_directory = get_summary_dir(base_dir)
    summary_file = summary_directory / CODE_SUMMARY_FILENAME
    project_root = base_dir.resolve()

    if not summary_directory.exists():
        print(f"Warning: Summary directory {summary_directory} does not exist. Skipping summary creation.", file=sys.stderr)
        return

    # Convert compressed_files to set for efficient lookup
    compressed_set = set(compressed_files) if compressed_files else set()

    try:
        gitignore_specs = file_utils.parse_gitignore(project_root)
        tree_output = file_utils.get_tree_output(project_root, gitignore_specs, file_utils.DEFAULT_IGNORE_LIST)

        with open(summary_file, "w", encoding='utf-8') as summary:
            summary.write(f"Project Root: {project_root}\n")
            summary.write(f"Project Structure:\n```\n{tree_output}\n```\n\n---\n")

            for file_path_str in selected_files: # selected_files should be absolute paths
                try:
                    file_path_obj = Path(file_path_str)
                    # Calculate relative path from project root for display
                    try:
                        relative_path = file_path_obj.relative_to(project_root)
                    except ValueError:
                        relative_path = file_path_obj # Fallback if not relative (shouldn't happen often)

                    lang_hint = file_path_obj.suffix.lstrip('.') if file_path_obj.suffix else ""

                    # Check if this file should use compressed summary
                    if file_path_str in compressed_set and client and llm_model:
                        summary.write(f"## File: {relative_path.as_posix()} [AI Compressed]\n\n")
                        print(f"Generating compressed summary for {relative_path.as_posix()}...")

                        # Read the file content
                        with open(file_path_obj, "r", encoding='utf-8') as f:
                            file_content = f.read()

                        # Generate compressed summary using AI
                        compressed_content = openai_utils.compress_single_file(
                            client,
                            llm_model,
                            str(relative_path.as_posix()),
                            file_content
                        )

                        if compressed_content:
                            summary.write(f"{compressed_content}\n\n---\n")
                        else:
                            # Fallback to full content if compression fails
                            summary.write(f"```{lang_hint}\n")
                            summary.write(file_content)
                            summary.write("\n```\n---\n")
                    else:
                        # Regular full content
                        summary.write(f"## File: {relative_path.as_posix()}\n\n")
                        summary.write(f"```{lang_hint}\n")
                        with open(file_path_obj, "r", encoding='utf-8') as f:
                            summary.write(f.read())
                        summary.write("\n```\n---\n")

                except FileNotFoundError:
                     summary.write(f"## File: {file_path_str}\n\nError: File not found.\n\n---\n")
                except Exception as e:
                     summary.write(f"## File: {file_path_str}\n\nError reading file: {e}\n\n---\n")
    except IOError as e:
        print(f"Error writing local code summary file {summary_file}: {e}", file=sys.stderr)
    except Exception as e:
         print(f"An unexpected error occurred during local code summary creation: {e}", file=sys.stderr)


def create_compressed_summary(
    selected_files: list[str],
    client: OpenAI | None,
    llm_model: str,
    base_dir: Path = Path('.')
    ):
    """Creates a compressed summary markdown file using AI for non-main files."""
    summary_directory = get_summary_dir(base_dir)
    compressed_summary_file = summary_directory / COMPRESSED_SUMMARY_FILENAME
    project_root = base_dir.resolve()

    if not summary_directory.exists():
         print(f"Warning: Summary directory {summary_directory} does not exist. Skipping compressed summary generation.", file=sys.stderr)
         return # Or create it: create_hidden_directory()

    if not client:
        print("OpenAI client not available. Cannot generate compressed summary.", file=sys.stderr)
        # Optionally create a file indicating the error or just skip
        return

    try:
        gitignore_specs = file_utils.parse_gitignore(project_root)
        tree_output = file_utils.get_tree_output(project_root, gitignore_specs, file_utils.DEFAULT_IGNORE_LIST)

        # Overwrite existing compressed summary
        with open(compressed_summary_file, "w", encoding='utf-8') as summary:
            summary.write(f"Project Root: {project_root}\n")
            summary.write(f"Project Structure:\n```\n{tree_output}\n```\n\n---\n")

            for file_path_str in selected_files: # Absolute paths
                file_path_obj = Path(file_path_str)
                try:
                    relative_path = file_path_obj.relative_to(project_root)
                    relative_path_str = relative_path.as_posix()
                except ValueError:
                    relative_path = file_path_obj # Fallback
                    relative_path_str = str(file_path_obj)


                # Define metadata path based on relative structure *within* .summary_files
                metadata_dir_relative = relative_path.parent # Relative path of the dir
                metadata_directory = summary_directory / metadata_dir_relative
                metadata_directory.mkdir(parents=True, exist_ok=True)
                metadata_path = metadata_directory / f"{file_path_obj.name}{METADATA_SUFFIX}"

                file_summary = "" # Initialize summary variable

                # --- AI Summary Generation with Hashing ---
                try:
                    with open(file_path_obj, "r", encoding='utf-8') as f:
                        file_content = f.read()
                    current_hash = hashlib.md5(file_content.encode("utf-8")).hexdigest()
                except Exception as e:
                    print(f"Error reading file {relative_path_str} for hashing: {e}", file=sys.stderr)
                    summary.write(f"\n## File: {relative_path_str}\n\nError reading file: {e}\n---\n")
                    continue # Skip this file

                # Check cache
                use_cached = False
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r", encoding='utf-8') as metadata_file:
                            metadata = json.load(metadata_file)
                        saved_hash = metadata.get("hash")
                        if saved_hash == current_hash:
                            print(f"File '{relative_path_str}' unchanged. Using cached summary.")
                            file_summary = metadata.get("summary", "Error: Cached summary not found.")
                            use_cached = True
                        else:
                            print(f"File '{relative_path_str}' modified. Generating new summary...")
                    except json.JSONDecodeError:
                        print(f"Warning: Corrupted metadata for {relative_path_str}. Regenerating summary.", file=sys.stderr)
                    except Exception as e:
                         print(f"Error reading metadata for {relative_path_str}: {e}. Regenerating summary.", file=sys.stderr)

                # Generate summary if not cached or cache invalid/missing
                if not use_cached:
                     print(f"Generating summary for {relative_path_str}...")
                     # Call the utility function
                     file_summary = openai_utils.generate_summary(client, llm_model, file_content)
                     # Cache the new summary and hash
                     metadata = {"hash": current_hash, "summary": file_summary}
                     try:
                         with open(metadata_path, "w", encoding='utf-8') as metadata_file:
                             json.dump(metadata, metadata_file, indent=4)
                     except Exception as e:
                         print(f"Error writing metadata for {relative_path_str}: {e}", file=sys.stderr)


                # Write summary to the compressed file
                summary.write(f"\n## File: {relative_path_str}\n\nSummary:\n```markdown\n") # Assume summary is markdownish
                summary.write(file_summary)
                summary.write("\n```\n---\n")
                print(f"Processed summary for: {relative_path_str}")
                print("-----------------------------------")


    except IOError as e:
        print(f"Error writing compressed summary file {compressed_summary_file}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred during compressed summary creation: {e}", file=sys.stderr)


def copy_summary_to_clipboard(base_dir: Path = Path('.')):
    """Copies the content of the local code_summary.md to the clipboard."""
    summary_file_path = get_summary_dir(base_dir) / CODE_SUMMARY_FILENAME
    if summary_file_path.exists():
        try:
            with open(summary_file_path, "r", encoding='utf-8') as summary_file:
                summary_content = summary_file.read()
            pyperclip.copy(summary_content)
            print("Local code summary content has been copied to clipboard.")
            return True
        except pyperclip.PyperclipException as e:
            print(f"Could not copy to clipboard: {e}. You can manually copy from {summary_file_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error reading summary file for clipboard: {e}", file=sys.stderr)
    else:
        print("Local code summary file not found, skipping clipboard copy.", file=sys.stderr)
    return False


def read_previous_collapsed_folders(base_dir: Path = Path('.')) -> list[str] | None:
    """Reads previously collapsed folder paths from JSON in the summary dir."""
    collapsed_folders_file = get_summary_dir(base_dir) / COLLAPSED_FOLDERS_FILENAME
    if collapsed_folders_file.exists():
        try:
            with open(collapsed_folders_file, "r", encoding='utf-8') as f:
                previous_collapsed = json.load(f)
            # Basic validation: ensure it's a list of strings
            if isinstance(previous_collapsed, list) and all(isinstance(item, str) for item in previous_collapsed):
                return previous_collapsed
            else:
                print(
                    f"Warning: Invalid format in {collapsed_folders_file}. Ignoring.", file=sys.stderr)
                return None
        except json.JSONDecodeError:
            print(
                f"Warning: Could not decode {collapsed_folders_file}. Ignoring.", file=sys.stderr)
            return None
        except IOError as e:
            print(
                f"Warning: Could not read {collapsed_folders_file}: {e}. Ignoring.", file=sys.stderr)
            return None
    else:
        return None


def write_previous_collapsed_folders(collapsed_folders: list[str], base_dir: Path = Path('.')):
    """Writes the list of collapsed folder paths to JSON."""
    hidden_directory = get_summary_dir(base_dir)
    collapsed_folders_file = hidden_directory / COLLAPSED_FOLDERS_FILENAME
    if not hidden_directory.exists():
        # Attempt to create it if missing
        create_hidden_directory(base_dir)
        if not hidden_directory.exists(): # Check again if creation failed
             print(f"Warning: Cannot save collapsed folders, directory {hidden_directory} not found/creatable.", file=sys.stderr)
             return
    try:
        # Ensure collapsed_folders is a list of strings
        if isinstance(collapsed_folders, list) and all(isinstance(item, str) for item in collapsed_folders):
            with open(collapsed_folders_file, "w", encoding='utf-8') as f:
                json.dump(collapsed_folders, f, indent=4)
        else:
            print("Error: Invalid data type for collapsed_folders. Cannot save collapsed folders.", file=sys.stderr)
    except IOError as e:
        print(f"Error writing collapsed folders file {collapsed_folders_file}: {e}", file=sys.stderr)
    except TypeError as e:
        print(f"Error serializing collapsed folders data to JSON: {e}", file=sys.stderr)


# --- Selection Configuration Management ---

def read_selection_configs(base_dir: Path = Path('.')) -> dict:
    """Reads saved selection configurations from JSON."""
    configs_file = get_summary_dir(base_dir) / SELECTION_CONFIGS_FILENAME
    if configs_file.exists():
        try:
            with open(configs_file, "r", encoding='utf-8') as f:
                configs = json.load(f)
            if isinstance(configs, dict):
                return configs
            else:
                print(f"Warning: Invalid format in {configs_file}. Ignoring.", file=sys.stderr)
                return {}
        except json.JSONDecodeError:
            print(f"Warning: Could not decode {configs_file}. Ignoring.", file=sys.stderr)
            return {}
        except IOError as e:
            print(f"Warning: Could not read {configs_file}: {e}. Ignoring.", file=sys.stderr)
            return {}
    else:
        return {}


def write_selection_configs(configs: dict, base_dir: Path = Path('.')):
    """Writes selection configurations to JSON."""
    configs_file = get_summary_dir(base_dir) / SELECTION_CONFIGS_FILENAME
    try:
        with open(configs_file, "w", encoding='utf-8') as f:
            json.dump(configs, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not write to {configs_file}: {e}", file=sys.stderr)
    except TypeError as e:
        print(f"Error serializing configs to JSON: {e}", file=sys.stderr)


def save_selection_config(name: str, selected_files: list[str], compressed_files: list[str], base_dir: Path = Path('.')):
    """Saves a named selection configuration."""
    configs = read_selection_configs(base_dir)
    configs[name] = {
        "selected_files": selected_files,
        "compressed_files": compressed_files
    }
    write_selection_configs(configs, base_dir)


def load_selection_config(name: str, base_dir: Path = Path('.')) -> tuple[list[str], list[str]] | None:
    """Loads a named selection configuration. Returns (selected_files, compressed_files) or None."""
    configs = read_selection_configs(base_dir)
    if name in configs:
        config = configs[name]
        selected = config.get("selected_files", [])
        compressed = config.get("compressed_files", [])
        return (selected, compressed)
    return None


def delete_selection_config(name: str, base_dir: Path = Path('.')):
    """Deletes a named selection configuration."""
    configs = read_selection_configs(base_dir)
    if name in configs:
        del configs[name]
        write_selection_configs(configs, base_dir)
        return True
    return False


def rename_selection_config(old_name: str, new_name: str, base_dir: Path = Path('.')):
    """Renames a selection configuration."""
    configs = read_selection_configs(base_dir)
    if old_name in configs and new_name not in configs:
        configs[new_name] = configs[old_name]
        del configs[old_name]
        write_selection_configs(configs, base_dir)
        return True
    return False