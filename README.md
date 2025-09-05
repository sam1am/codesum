# CodeSum: AI-Powered Code Summarizer with TUI 🐍📄✨

**Generate concise code summaries optimized for Large Language Models (LLMs) using an interactive Text User Interface (TUI).**

This tool analyzes your project structure, lets you select relevant files through an interactive TUI, and generates summaries tailored for AI interaction. It can create both a full-content summary (copied to your clipboard) and an AI-powered compressed summary, leveraging models like GPT-4o via the OpenAI API. Features include intelligent summary caching, `.gitignore` respect, and optional AI-driven README generation based on the compressed summary.

## Model Context Protocol (MCP) Server 🌐

CodeSum now includes an MCP (Model Context Protocol) server that allows other AI tools to interact with your codebase programmatically. The MCP server can intelligently select relevant files based on a query and return structured summaries that can be used as context for LLM interactions.

## Video Tutorial (Demonstrates Core Functionality)

[![codesum youtube video](https://img.youtube.com/vi/IY-KIMyUaB8/0.jpg)](https://www.youtube.com/watch?v=IY-KIMyUaB8)
*(Note: The video might show older setup steps, but the core TUI and summarization process remains similar.)*

## Key Features 🔑

*   **Interactive TUI:** Uses `curses` for a smooth file selection experience directly in your terminal.
*   **Smart Selection:** Remembers your previously selected files for the project.
*   **Respects `.gitignore`:** Automatically excludes files and directories listed in your `.gitignore`.
*   **Configurable Ignores:** Uses a default list of common ignores (like `.git`, `venv`, `node_modules`) in addition to `.gitignore`.
*   **Dual Summaries:**
    *   **Local Summary:** Creates a `code_summary.md` with the full content of selected files and project structure (automatically copied to clipboard).
    *   **AI Compressed Summary:** (Optional) Generates a `compressed_code_summary.md` using an LLM for concise summaries of each file, ideal for large context windows.
*   **Intelligent Caching:** AI summaries are cached based on file content hashes, avoiding redundant API calls for unchanged files.
*   **AI README Generation:** (Optional) Updates or creates a `README.md` in your project root using the AI-generated compressed summary.
*   **Easy Configuration:** Manage your OpenAI API key and preferred model via a simple command (`codesum --configure`) or during the first run. Configuration is stored securely in your user config directory.
*   **Cross-Platform:** Works on Linux, macOS, and Windows (includes necessary `windows-curses` dependency).
*   **PyPI Package:** Easily installable via `pip`.

## Installation 🛠️

Requires Python 3.8 or higher.

### Option 1: From PyPI (Recommended)

This is the standard and recommended way to install `CodeSum`:

```sh
pip install codesum
```


This command downloads the package from the Python Package Index (PyPI) and installs it along with its dependencies. The codesum command will then be available in your environment.

Option 2: From Source (for Development or Latest Version)

If you want to install directly from the source code (e.g., for development or to get the absolute latest changes not yet released on PyPI):

Clone the repository:

```sh
git clone https://github.com/sam1am/codesum.git
cd codesum
```

Create and activate a virtual environment (highly recommended):

```sh
python3 -m venv venv
source venv/bin/activate # On Windows use `.\venv\Scripts\activate`
```

Install the package:

For a regular install from source:

```sh
pip install .
```

For an editable install (changes in the source code are reflected immediately):

```sh
pip install -e .
```

Configuration

CodeSum needs your OpenAI API key to use AI features.

Run the configuration wizard after installation:

```sh
codesum --configure
```

This will interactively prompt you for your OpenAI API Key and the desired LLM model (e.g., gpt-4o).

Alternatively, the tool will prompt you for the API key on the first run if it's not already configured.

Configuration is saved in a settings.env file within your user's config directory (e.g., ~/.config/codesum on Linux, ~/Library/Application Support/codesum on macOS, %APPDATA%\codesum\codesum on Windows). You can leave the API key blank if you only want to use the local summary and clipboard features.

## Usage 🚀

Navigate to your project's root directory in your terminal.

Run the command:

```sh
codesum
```

The interactive TUI will launch, allowing you to select files using the arrow keys and spacebar.

[SPACE] : Toggle selection for the highlighted file.

[↑↓] : Navigate up/down.

[←→ / PgUp / PgDn] : Navigate pages.

[ENTER] : Confirm selection and proceed.

[Q / ESC] : Quit without saving changes.

After confirming your selection, the tool will:

Create/update .summary_files/code_summary.md.

Copy the content of code_summary.md to your clipboard.

Save your selection in .summary_files/previous_selection.json.

If an OpenAI API key is configured:

It will ask if you want to generate an AI-powered compressed summary (.summary_files/compressed_code_summary.md).

If the compressed summary is generated, it will ask if you want to generate/update the root README.md file based on it.

## MCP Server Usage 🌐

CodeSum includes an MCP (Model Context Protocol) server that can be used by other AI tools to interact with your codebase programmatically.

To start the MCP server:

```sh
codesum --mcp-server
```

By default, the server will run on `localhost:8000`. You can specify a different host and port:

```sh
codesum --mcp-server --mcp-host 0.0.0.0 --mcp-port 8001
```

The MCP server provides the following endpoints:

- `GET /health` - Health check endpoint
- `GET /summarize?query=<query>&max_files=<N>` - Generate summary with query parameters
- `POST /summarize` - Generate summary with JSON body

See [MCP_USAGE.md](MCP_USAGE.md) for detailed API documentation and usage examples.

## Output 📂

## Output 📂

The tool creates a hidden .summary_files directory in your project root containing:

code_summary.md:

Contains the project structure tree and the full concatenated content of all selected files.

This content is automatically copied to your clipboard.

compressed_code_summary.md (Optional - requires API key):

Contains the project structure tree and AI-generated summaries for each selected file.

previous_selection.json:

Stores the absolute paths of the files you selected in the last run for this project.

[filename]_metadata.json (Optional - in subdirs matching source):

JSON files (one per AI-summarized file) storing the file's content hash and the generated AI summary for caching purposes.

Additionally, if you opt-in:

README.md (Optional - requires API key):

The project's main README file may be created or updated with AI-generated content based on the compressed summary.

And for configuration:

settings.env (Located in user config directory, not project dir):

Stores your OPENAI_API_KEY and LLM_MODEL.

## Dependencies 📚

Core dependencies (installed automatically via pip):

openai

pathspec

python-dotenv

pyperclip

platformdirs

windows-curses (on Windows only)

importlib-resources (on Python < 3.9 only)

## License 📜

This project is licensed under the MIT License.

## Acknowledgements 🙌

Thanks to the creators of the libraries used in this project and to everyone contributing to the open-source community.