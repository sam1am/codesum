import os
import curses
import json
import hashlib
from pathlib import Path
from ItsPrompt.prompt import Prompt
from openai import OpenAI
from dotenv import load_dotenv
import argparse
import pathspec
import pyperclip


load_dotenv()

IGNORE_LIST = [".git", "venv", ".summary_files"]

LLM_MODEL=os.getenv("LLM_MODEL", "gpt-4o")
print(f"Using model: {LLM_MODEL}")

def build_tree(directory, gitignore_specs, ignore_list):
    tree = {}
    for root, dirs, files in os.walk(directory):
        # Convert paths to relative paths for gitignore matching
        rel_root = os.path.relpath(root, directory)
        
        # Filter directories
        dirs[:] = [d for d in dirs 
                  if d not in ignore_list and 
                  not (gitignore_specs and gitignore_specs.match_file(os.path.join(rel_root, d) + '/'))]
        
        current = tree
        path = root.split(os.sep)[1:]  # Skip the '.' at the beginning
        for part in path:
            current = current.setdefault(part, {})
        
        # Filter files
        for file in files:
            rel_path = os.path.join(rel_root, file)
            if not (gitignore_specs and gitignore_specs.match_file(rel_path)):
                current[file] = os.path.join(root, file)
    
    return tree

def flatten_tree(tree, prefix=''):
    items = []
    for key, value in sorted(tree.items()):
        if isinstance(value, dict):
            items.append((f"{prefix}{key}/", None))
            items.extend(flatten_tree(value, prefix=f"{prefix}{key}/"))
        else:
            items.append((f"{prefix}{key}", value))
    return items


def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate code summaries and README.")
    parser.add_argument("--infer", action="store_true", help="Enable OpenAI calls for summaries and readme")
    return parser.parse_args()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Creates a hidden directory to store the summary files
def create_hidden_directory():
    hidden_directory = Path(".summary_files")
    if not hidden_directory.exists():
        hidden_directory.mkdir()

def get_tree_output():
    def walk_directory_tree(directory, level, gitignore_specs):
        output = ""
        entries = os.listdir(directory)
        for entry in sorted(entries):
            entry_path = os.path.join(directory, entry)
            # Convert to relative path for gitignore matching
            relative_entry_path = os.path.relpath(entry_path, ".")
            
            # Add trailing slash for directories when checking gitignore
            check_path = relative_entry_path + '/' if os.path.isdir(entry_path) else relative_entry_path
            
            # Check if the entry should be ignored
            if not any(ignore_item in relative_entry_path for ignore_item in IGNORE_LIST):
                if not (gitignore_specs and gitignore_specs.match_file(check_path)):
                    if os.path.isfile(entry_path):
                        output += f"{' ' * (4 * level)}|-- {entry}\n"
                    elif os.path.isdir(entry_path):
                        output += f"{' ' * (4 * level)}|-- {entry}\n"
                        output += walk_directory_tree(entry_path, level + 1, gitignore_specs)
        return output

    gitignore_specs = parse_gitignore()
    tree_output = walk_directory_tree(".", 0, gitignore_specs)
    return tree_output

def generate_summary(file_content):
    print("Waiting for summary. This may take a few minutes...")

    # Make the call to the OpenAI API to generate the summary
    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "You are a code documenter. Your purpose is to provide useful summaries for "
                                          "inclusion as reference for future prompts. Provide a concise summary of the "
                                          "given code and any notes that will be useful for other ChatBots to understand how it works. "
                                          "Include specific documentation about each function, class, and relevant parameters."},
            {"role": "user", "content": file_content}
        ],
        max_tokens=2500
    )
    
    # Access the completion choice content directly
    summary = completion.choices[0].message.content
    return summary

def generate_readme(compressed_summary):
    print("Generating updated READMfE.md file...")

    # Make the call to the OpenAI API to generate the README content
    completion = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "You are a code documenter. Your task is to create an updated README.md file for a project "
                                          "using the compressed code summary provided. Make it look nice, use emoji, and include the "
                                          "following sections: Project Description, Installation, and Usage. You can also include a "
                                          "section for Acknowledgements and a section for License."},
            {"role": "user", "content": compressed_summary}
        ],
        max_tokens=1500
    )
    
    # Access the completion choice content directly
    readme_content = completion.choices[0].message.content
    return readme_content


def create_compressed_summary(selected_files):
    summary_directory = Path(".summary_files")
    compressed_summary_file = summary_directory / "compressed_code_summary.md"
    if compressed_summary_file.exists():
        compressed_summary_file.unlink()

    with open(compressed_summary_file, "a") as summary:
        # Include the output of the tree command at the beginning
        tree_output = get_tree_output()
        summary.write(f"Output of tree command:\n```\n{tree_output}\n```\n\n---\n")

        for file in selected_files:

            file_path = Path(file)
            relative_path = file_path.relative_to(".")
            metadata_directory = summary_directory / relative_path.parent
            metadata_directory.mkdir(parents=True, exist_ok=True)
            metadata_path = metadata_directory / f"{file_path.name}_metadata.json"


            if file == "main.py":
                summary.write(f"\n{file}\n```\n")
                with open(file, "r") as f:
                    file_content = f.read()
                    summary.write(file_content)
                summary.write("```\n---\n")
            else:
                if metadata_path.exists():
                    print(f"File {file} has been summarized before. Checking if it has been modified...")
                    with open(metadata_path, "r") as metadata_file:
                        metadata = json.load(metadata_file)
                    saved_hash = metadata["hash"]

                    with open(file, "r") as f:
                        file_content = f.read()
                    current_hash = hashlib.md5(file_content.encode("utf-8")).hexdigest()

                    if saved_hash == current_hash:
                        print(f"File {file} has not been modified. Using saved summary...")
                        file_summary = metadata["summary"]
                    else:
                        print(f"File {file} has been modified. Generating new summary...")
                        file_summary = generate_summary(file_content)
                        metadata = {"hash": current_hash, "summary": file_summary}
                        with open(metadata_path, "w") as metadata_file:
                            json.dump(metadata, metadata_file)
                else:
                    print(f"File {file} has not been summarized before. Generating summary...")
                    with open(file, "r") as f:
                        file_content = f.read()
                    file_summary = generate_summary(file_content)
                    current_hash = hashlib.md5(file_content.encode("utf-8")).hexdigest()
                    metadata = {"hash": current_hash, "summary": file_summary}
                    with open(metadata_path, "w") as metadata_file:
                        json.dump(metadata, metadata_file)

                print(f"Saving summary for {file}...")

                summary.write(f"\n{file}\n```\n")
                summary.write(file_summary)
                summary.write("```\n---\n")

                print("-----------------------------------")


def parse_gitignore():
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            gitignore_content = f.read()
        gitignore_specs = pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, gitignore_content.splitlines())
    else:
        gitignore_specs = None
    return gitignore_specs

def display_files():
    print("List of files in the current directory and its subdirectories:")
    files = []
    gitignore_specs = parse_gitignore()
    for root, _, filenames in os.walk("."):
        # Convert to relative path for gitignore matching
        rel_root = os.path.relpath(root, ".")
        
        # Check if the root directory is in the IGNORE_LIST
        if not any(ignore_item in rel_root for ignore_item in IGNORE_LIST):
            for filename in filenames:
                rel_path = os.path.join(rel_root, filename)
                if not (gitignore_specs and gitignore_specs.match_file(rel_path)):
                    files.append(os.path.join(root, filename))
    return files



def select_files(directory, previous_selection, gitignore_specs, ignore_list):
    tree = build_tree(directory, gitignore_specs, ignore_list)
    flattened_tree = flatten_tree(tree)
    
    options = []
    file_paths = {}
    for item, path in flattened_tree:
        if path:
            options.append((item, item))
            file_paths[item] = path
        else:
            options.append((f"[{item}]", item))

    def draw_menu(stdscr, current_page, current_pos):
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        
        page_size = h - 4  # Leave room for instructions and status line
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(options))
        current_options = options[start_idx:end_idx]

        stdscr.addstr(0, 0, "Use UP/DOWN arrows to navigate, SPACE to select/deselect, ENTER to confirm.")
        stdscr.addstr(1, 0, "Use LEFT/RIGHT arrows to change pages.")
        
        for idx, (item, _) in enumerate(current_options):
            if idx == current_pos:
                attr = curses.A_REVERSE  # Highlight the current position
            else:
                attr = curses.A_NORMAL
            
            if item in selected:
                stdscr.addstr(idx + 2, 0, f"[X] {item}", attr)
            else:
                stdscr.addstr(idx + 2, 0, f"[ ] {item}", attr)
        
        total_pages = (len(options) + page_size - 1) // page_size
        status = f"Page {current_page + 1}/{total_pages} | Items {start_idx + 1}-{end_idx} of {len(options)}"
        stdscr.addstr(h-1, 0, status)
        
        stdscr.refresh()

    def curses_main(stdscr):
        nonlocal selected
        curses.curs_set(0)  # Hide the cursor
        current_page = 0
        current_pos = 0
        page_size = curses.LINES - 4  # Leave room for instructions and status line

        while True:
            draw_menu(stdscr, current_page, current_pos)
            key = stdscr.getch()

            if key == ord(' '):  # Spacebar
                item = options[current_page * page_size + current_pos][0]
                if item in selected:
                    selected.remove(item)
                else:
                    selected.add(item)
            elif key == curses.KEY_UP and current_pos > 0:
                current_pos -= 1
            elif key == curses.KEY_DOWN and current_pos < min(page_size - 1, len(options) - current_page * page_size - 1):
                current_pos += 1
            elif key == curses.KEY_LEFT and current_page > 0:
                current_page -= 1
                current_pos = 0
            elif key == curses.KEY_RIGHT and (current_page + 1) * page_size < len(options):
                current_page += 1
                current_pos = 0
            elif key == 10:  # Enter key
                return

    selected = set(item for item, _ in options if file_paths.get(item) in previous_selection)
    curses.wrapper(curses_main)

    return [file_paths[item] for item in selected if item in file_paths]


def create_code_summary(selected_files):
    summary_directory = Path(".summary_files")
    summary_file = summary_directory / "code_summary.md"
    if summary_file.exists():
        summary_file.unlink()
    with open(summary_file, "a") as summary:
        # Include the output of the tree command at the beginning
        tree_output = get_tree_output()
        summary.write(f"Output of tree command:\n```\n{tree_output}\n```\n\n---\n")

        for file_path in selected_files:
            summary.write(f"```{file_path}\n")  # Put filepath on same line as opening ```
            with open(file_path, "r") as f:
                summary.write(f.read())
            summary.write("\n```\n---\n")  # Add newline before closing ```

def read_previous_selection():
    hidden_directory = Path(".summary_files") 
    selection_file = hidden_directory / "previous_selection.json" 
    if selection_file.exists():
        with open(selection_file, "r") as f: 
            previous_selection = json.load(f)
        return previous_selection
    else:
        return []

def write_previous_selection(selected_files):
    hidden_directory = Path(".summary_files")  
    with open(hidden_directory / "previous_selection.json", "w") as f: 
        json.dump(selected_files, f)

def main():
    create_hidden_directory()
    
    gitignore_specs = parse_gitignore()
    ignore_list = IGNORE_LIST
    
    previous_selection = read_previous_selection()
    selected_files = select_files(".", previous_selection, gitignore_specs, ignore_list)
    
    # Save the selected files
    write_previous_selection(selected_files)
    
    # Create the local code summary
    create_code_summary(selected_files)
    print("\nLocal code summary successfully created in '.summary_files/code_summary.md'.")

    # Copy code_summary.md contents to clipboard
    summary_file_path = Path(".summary_files") / "code_summary.md"
    with open(summary_file_path, "r") as summary_file:
        summary_content = summary_file.read()
    pyperclip.copy(summary_content)
    print("Code summary has been copied to clipboard.")

    # Ask user if they want to generate a compressed summary
    generate_compressed = input("\nDo you want to generate a compressed summary of the selected files? (y/N): ").lower() == 'y'

    if generate_compressed:
        create_compressed_summary(selected_files)
        print("\nCompressed code summary successfully created in '.summary_files/compressed_code_summary.md'.")
        
        # Ask user if they want to generate an updated README
    generate_readme_file = input("\nDo you want to generate an updated README.md file? (y/N): ").lower() == 'y'

    if generate_readme_file:
        # Load compressed code summary
        summary_directory = Path(".summary_files")
        compressed_summary_file = summary_directory / "compressed_code_summary.md"
        with open(compressed_summary_file, "r") as f:
            compressed_summary = f.read()

        # Generate updated README.md file using GPT-4
        readme_content = generate_readme(compressed_summary)

        # Save the updated README.md file
        readme_file = Path("README.md")
        with open(readme_file, "w") as f:
            f.write(readme_content)

        print("\nUpdated README.md file successfully generated in 'README.md'.")

if __name__ == "__main__":
    main()



