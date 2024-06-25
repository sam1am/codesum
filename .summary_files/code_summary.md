Output of tree command:
```
|-- LICENSE
|-- README.md
|-- app.py
|-- codesum.sh
|-- env_example
|-- requirements.txt
|-- setup.py

```

---

./setup.py
```
#!/usr/bin/env python3

import os
import subprocess
import sys
import platform
from pathlib import Path
import shutil

def is_windows():
    return platform.system().lower() == "windows"

def get_script_dir():
    return Path(__file__).parent.absolute()

def setup_virtualenv_and_run_script(script_dir):
    venv_activate = script_dir / 'venv' / 'bin' / 'activate'
    run_command = f'source {venv_activate} && python {script_dir / "app.py"}'
    return run_command

def get_shell_configuration_path():
    if is_windows():
        return Path.home() / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
    elif platform.system().lower() == "darwin":
        return Path.home() / ".zshrc"
    else:
        return Path.home() / ".bashrc"

def create_virtual_environment(script_dir):
    venv_path = script_dir / "venv"
    if not venv_path.is_dir():
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)])
    return venv_path

def activate_virtual_environment(venv_path):
    if is_windows():
        activate_script = venv_path / "Scripts" / "activate.bat"
        os.system(f'cmd /k "{activate_script}"')
    else:
        activate_script = venv_path / "bin" / "activate"
        os.environ["VIRTUAL_ENV"] = str(venv_path)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{str(venv_path / 'bin')}{os.pathsep}{old_path}"
        subprocess.run(["source", str(activate_script)], shell=True)

def install_dependencies(script_dir, venv_path):
    requirements_path = script_dir / "requirements.txt"
    if requirements_path.is_file():
        subprocess.run(["pip", "install", "-r", str(requirements_path)])
    else:
        print("No requirements.txt found.")

def set_alias(run_command):
    shell_config_path = get_shell_configuration_path()
    alias_name = "codesum"
    alias_command = f'alias {alias_name}="{run_command}"'
    
    if shell_config_path.is_file():
        with open(shell_config_path, "r+") as file:
            content = file.read()
            if alias_command not in content:
                file.write(f"\n# Alias for code_summarize script\n{alias_command}\n")
                print(f"Alias added to {shell_config_path}. Please restart your shell or run 'source {shell_config_path}' to use it.")
            else:
                print("Alias already exists in your shell profile.")

def check_and_create_env_file(script_dir):
    env_file = script_dir / ".env"
    env_example = script_dir / "env_example"

    if not env_file.exists():
        print("No .env file found. Creating one...")
        if env_example.exists():
            shutil.copy(env_example, env_file)
            print("Created .env file from env_example.")
        else:
            print("env_example not found. Creating a new .env file.")
            env_file.touch()

        openai_api_key = input("Please enter your OpenAI API key: ")
        llm_model = input("Enter the LLM model to use (default is gpt-4): ") or "gpt-4"

        with open(env_file, "w") as f:
            f.write(f"OPENAI_API_KEY={openai_api_key}\n")
            f.write(f"LLM_MODEL={llm_model}\n")

        print(".env file created successfully.")
    else:
        print(".env file already exists.")

def main():
    script_dir = get_script_dir()
    
    venv_path = create_virtual_environment(script_dir)
    activate_virtual_environment(venv_path)
    
    install_dependencies(script_dir, venv_path)
    
    check_and_create_env_file(script_dir)
    
    run_command = setup_virtualenv_and_run_script(script_dir)
    set_alias(run_command)

if __name__ == "__main__":
    main()
```
---

./requirements.txt
```
openai
itsprompt
pathspec
python-dotenv
keyboard
pyperclip```
---

./README.md
```
# Code Summarizer for LLM Interaction

## Project Description 📝

This tool generates concise code summaries optimized for Large Language Models (LLMs). It uses OpenAI's GPT-4 to create project overviews, making it easier for LLMs to understand and work with your codebase. Features include interactive file selection, summary caching, and automatic README generation.

## Key Features 🔑

- Curses-based interactive file selection
- Intelligent summary caching
- Respects `.gitignore` rules
- Generates detailed and compressed summaries
- Creates AI-generated README.md
- Command-line argument support

## Installation 🛠️

You can set up this project using either the automated setup script or manual installation.

### Option 1: Automated Setup (Recommended)

1. Clone the repository
2. Navigate to the project directory
3. Run the setup script:
   ```sh
   python setup.py
   ```
   This script will:
   - Create a virtual environment
   - Install dependencies
   - Set up the .env file
   - Create an alias for easy usage

### Option 2: Manual Setup

1. Clone the repository
2. Navigate to the project directory
3. Set up the Python environment:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Create a `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY='your-api-key-here'
   LLM_MODEL='gpt-4'
   ```
5. Optionally, run `codesum.sh` for automated setup

## Usage 🚀

### Python script:
```sh
python app.py [--infer]
```

### Bash script:
```sh
chmod +x codesum.sh
./codesum.sh [arguments]
```

### Using the alias (if set up):
```sh
codesum [arguments]
```

The `--infer` flag enables OpenAI API calls for summaries and README generation.

## Output 📂

When run, the script produces the following:

1. **Local Code Summary**: 
   - File: `.summary_files/code_summary.md`
   - Contents: A comprehensive summary of all selected files, including their full content and a tree structure of the project.

2. **Compressed Code Summary** (optional):
   - File: `.summary_files/compressed_code_summary.md`
   - Contents: A condensed version of the code summary, including AI-generated summaries for each file and the project structure.

3. **Updated README.md** (optional):
   - File: `README.md` in the project root
   - Contents: An AI-generated README file based on the compressed code summary, including sections like Project Description, Installation, Usage, and more.

4. **Metadata Files**:
   - Location: `.summary_files/[file_path]_metadata.json` for each summarized file
   - Contents: JSON files containing the hash of the original file and its generated summary, used for caching purposes.

5. **Previous Selection File**:
   - File: `.summary_files/previous_selection.json`
   - Contents: A JSON file storing the list of previously selected files for future reference.

These outputs provide a comprehensive overview of your project, facilitate efficient interaction with LLMs, and streamline future summarization processes.


## Dependencies 📚

- openai
- itsprompt
- pathspec
- python-dotenv
- keyboard
- curses (built-in)

## Acknowledgements 🙌

Thanks to all contributors and library creators.

## License 📜

[MIT License](LICENSE)```
---

./codesum.sh
```
#!/bin/bash

# Function to add alias to the profile if it doesn't exist
add_alias() {
    local profile_path=$1
    local alias_name=$2
    local script=$3

    # Check if this script is in the profile
    local alias_command="alias ${alias_name}='${script}'"
    if ! grep -q "${alias_command}" "${profile_path}"; then
        echo "${alias_command}" >> "${profile_path}"
        echo "Alias added. You might need to restart your terminal or run 'source ${profile_path}'"
    else
        echo "Alias already exists in your profile"
    fi
}

#get the path of the script
SCRIPT=$(readlink -f "$0")
SCRIPTPATH=$(dirname "$SCRIPT")
GRANDPARENTDIR=$(dirname "$(dirname "$SCRIPTPATH")")

echo "$SCRIPT"
echo "$SCRIPTPATH"
echo "$GRANDPARENTDIR"

#see if virtual environment exists
if [ -f "$SCRIPTPATH/venv/bin/activate" ]; then
    echo "venv exists"
else
    echo "venv does not exist"
    #create virtual environment
    python3 -m venv "$SCRIPTPATH/venv"
    #activate virtual environment
    source "$SCRIPTPATH/venv/bin/activate"
    #install requirements
    pip install -r "$SCRIPTPATH/requirements.txt"
    #deactivate virtual environment
    deactivate
fi

# Alias handling
DECLINE_RECORD=~/.bash_alias_decline
BASH_PROFILE_PATH=~/.bash_profile
BASHRC_PATH=~/.bashrc

# Determine which shell profile exists
if [ -f "$BASH_PROFILE_PATH" ]; then
    PROFILE_PATH="$BASH_PROFILE_PATH"
elif [ -f "$BASHRC_PATH" ]; then
    PROFILE_PATH="$BASHRC_PATH"
else
    echo "No .bash_profile or .bashrc detected. Alias will not be added."
    exit 1
fi

ALIAS_NAME="code_summarize"
ALIAS_EXISTS=$(grep -Fq "alias $ALIAS_NAME=" "$PROFILE_PATH" && echo 'yes' || echo 'no')

# Check if the alias doesn't exist and the user hasn't previously declined
if [[ "$ALIAS_EXISTS" == "no" && ! -f "$DECLINE_RECORD" ]]; then
    echo "Alias not found in your profile. Do you want to add it? (yes/no)"
    read user_input
    if [[ $user_input == 'yes' ]]; then
        add_alias "$PROFILE_PATH" "$ALIAS_NAME" "$SCRIPT"
    elif [[ $user_input == 'no' ]]; then
        # Record the user's decision to not add the alias
        touch "$DECLINE_RECORD"
        echo "Okay, not adding alias. This decision has been remembered."
    fi
fi

# Activate the virtual environment
source "$SCRIPTPATH/venv/bin/activate"

# Run the app
# python "$SCRIPTPATH/app.py"
# Run the app with all command-line arguments passed to this script
python "$SCRIPTPATH/app.py" $@


# Deactivate the virtual environment
deactivate
```
---

./env_example
```
OPENAI_API_KEY=sk-XXXXXX
LLM_MODEL=gpt-4o```
---

./app.py
```
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

LLM_MODEL=os.getenv("LLM_MODEL")
print(f"Using model: {LLM_MODEL}")

def build_tree(directory, gitignore_specs, ignore_list):
    tree = {}
    for root, dirs, files in os.walk(directory):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_list and (gitignore_specs is None or not gitignore_specs.match_file(d))]
        
        current = tree
        path = root.split(os.sep)[1:]  # Skip the '.' at the beginning
        for part in path:
            current = current.setdefault(part, {})
        
        for file in files:
            if gitignore_specs is None or not gitignore_specs.match_file(os.path.join(root, file)):
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
        for entry in sorted(os.listdir(directory)):
            entry_path = os.path.join(directory, entry)
            relative_entry_path = os.path.relpath(entry_path, ".")

            # Check if the entry is not in the IGNORE_LIST
            if not any(ignore_item in entry_path for ignore_item in IGNORE_LIST):
                if gitignore_specs is None or not gitignore_specs.match_file(relative_entry_path):
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

        # Check if the root directory is in the IGNORE_LIST
        if not any(ignore_item in root for ignore_item in IGNORE_LIST):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                if gitignore_specs is None or not gitignore_specs.match_file(file_path):
                    files.append(file_path)
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
            summary.write(f"\n{file_path}\n```\n")
            with open(file_path, "r") as f:
                summary.write(f.read())
            summary.write("```\n---\n")




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
    generate_compressed = input("\nDo you want to generate a compressed summary of the selected files? (y/n): ").lower() == 'y'

    if generate_compressed:
        create_compressed_summary(selected_files)
        print("\nCompressed code summary successfully created in '.summary_files/compressed_code_summary.md'.")
        
        # Ask user if they want to generate an updated README
    generate_readme_file = input("\nDo you want to generate an updated README.md file? (y/n): ").lower() == 'y'

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



```
---
