# Code Summarizer for LLM Interaction

## Project Description 📝

This tool generates concise code summaries optimized for Large Language Models (LLMs). It uses OpenAI's GPT-4 to create project overviews, making it easier for LLMs to understand and work with your codebase. Features include interactive file selection, summary caching, and automatic README generation.

## Video Tutorial

[![codesum youtube video](https://img.youtube.com/vi/IY-KIMyUaB8/0.jpg)](https://www.youtube.com/watch?v=IY-KIMyUaB8)

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
   - The contents of this file will automatically be sent to the system clipboard.

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

[Apache 2.0](LICENSE)