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
CODE_SUMMARY_FILENAME = "code_summary.md"
COMPRESSED_SUMMARY_FILENAME = "compressed_code_summary.md"
SELECTION_FILENAME = "previous_selection.json"
METADATA_SUFFIX = "_metadata.json"

def get_summary_dir(base_dir: Path = Path('.')) -> Path:
    """Gets the path to the summary directory within the base directory."""
    return base_dir.resolve() / SUMMARY_DIR_NAME

def create_hidden_directory(base_dir: Path = Path('.')):
    """Creates the hidden summary directory if it doesn't exist."""
    hidden_directory = get_summary_dir(base_dir)
    try:
        hidden_directory.mkdir(exist_ok=True)
    except OSError as e:
        print(f"Error creating directory {hidden_directory}: {e}", file=sys.stderr)
        # Decide if this is fatal or not, maybe return False?
        # For now, just print error and continue

def read_previous_selection(base_dir: Path = Path('.')) -> list[str]:
    """Reads previously selected file paths from JSON in the summary dir."""
    selection_file = get_summary_dir(base_dir) / SELECTION_FILENAME
    if selection_file.exists():
        try:
            with open(selection_file, "r", encoding='utf-8') as f:
                previous_selection = json.load(f)
            # Basic validation: ensure it's a list of strings (absolute paths)
            if isinstance(previous_selection, list) and all(isinstance(item, str) for item in previous_selection):
                 # Convert to absolute paths if they aren't already, though they should be stored as such
                 return [str(Path(p).resolve()) for p in previous_selection]
            else:
                 print(f"Warning: Invalid format in {selection_file}. Ignoring.", file=sys.stderr)
                 return []
        except json.JSONDecodeError:
            print(f"Warning: Could not decode {selection_file}. Ignoring.", file=sys.stderr)
            return []
        except IOError as e:
            print(f"Warning: Could not read {selection_file}: {e}. Ignoring.", file=sys.stderr)
            return []
    else:
        return []

def write_previous_selection(selected_files: list[str], base_dir: Path = Path('.')):
    """Writes the list of selected absolute file paths to JSON."""
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
            with open(selection_file, "w", encoding='utf-8') as f:
                json.dump(abs_paths, f, indent=4)
        else:
            print("Error: Invalid data type for selected_files. Cannot save selection.", file=sys.stderr)
    except IOError as e:
        print(f"Error writing previous selection file {selection_file}: {e}", file=sys.stderr)
    except TypeError as e:
        print(f"Error serializing selection data to JSON: {e}", file=sys.stderr)


def create_code_summary(selected_files: list[str], base_dir: Path = Path('.')):
    """Creates a basic code summary file with full content of selected files."""
    summary_directory = get_summary_dir(base_dir)
    summary_file = summary_directory / CODE_SUMMARY_FILENAME
    project_root = base_dir.resolve()

    if not summary_directory.exists():
        print(f"Warning: Summary directory {summary_directory} does not exist. Skipping summary creation.", file=sys.stderr)
        return

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

                    summary.write(f"## File: {relative_path.as_posix()}\n\n") # Use relative path for header
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