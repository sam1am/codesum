import os
import sys
from openai import OpenAI, RateLimitError, APIError, APITimeoutError
from pathlib import Path
import tiktoken # Import tiktoken

# Conditional import for importlib.resources
if sys.version_info < (3, 9):
    import importlib_resources
    pkg_resources = importlib_resources
else:
    import importlib.resources as pkg_resources


def _load_prompt(prompt_filename: str) -> str:
    """Loads a prompt template from the package data."""
    try:
        # Use importlib.resources to access package data reliably
        resource_path = pkg_resources.files("codesum") / "prompts" / prompt_filename
        return resource_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        err_msg = f"Error: Prompt file '{prompt_filename}' not found in package data."
        print(err_msg, file=sys.stderr)
        return err_msg # Return error message as fallback prompt content
    except Exception as e:
        err_msg = f"Error reading prompt file '{prompt_filename}': {e}"
        print(err_msg, file=sys.stderr)
        return err_msg # Return error message as fallback prompt content


def generate_summary(client: OpenAI, model: str, file_content: str) -> str:
    """Generates a code summary using the OpenAI API."""
    if not client:
        return "Error: OpenAI client not available."

    system_prompt = _load_prompt("system_summary.md")
    if system_prompt.startswith("Error:"):
        return system_prompt # Return error if prompt loading failed

    print("Waiting for summary. This may take a few minutes...")
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": file_content}
            ],
            max_tokens=2500, # Consider making this configurable
            temperature=0.3 # Lower temperature for more focused summaries
        )
        summary = completion.choices[0].message.content
        return summary if summary else "Error: Empty summary received from API."
    except RateLimitError:
         print("Error: OpenAI API rate limit exceeded. Please try again later.", file=sys.stderr)
         return "Error: API rate limit exceeded."
    except APITimeoutError:
         print("Error: OpenAI API request timed out. Please try again later.", file=sys.stderr)
         return "Error: API request timed out."
    except APIError as e:
        print(f"Error: OpenAI API returned an error: {e}", file=sys.stderr)
        return f"Error: OpenAI API error: {e}"
    except Exception as e:
        print(f"Error calling OpenAI API for summary: {e}", file=sys.stderr)
        return f"Error generating summary: {e}"


def generate_readme(client: OpenAI, model: str, compressed_summary: str) -> str:
    """Generates a README.md file content using the OpenAI API."""
    if not client:
        return "Error: OpenAI client not available."

    system_prompt = _load_prompt("system_readme.md")
    if system_prompt.startswith("Error:"):
        return f"# README Generation Error\n\n{system_prompt}" # Return error

    print("Generating updated README.md file...")
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": compressed_summary}
            ],
            max_tokens=1500, # Consider making this configurable
            temperature=0.5 # Slightly higher temp for creative README
        )
        readme_content = completion.choices[0].message.content
        return readme_content if readme_content else "# README Generation Error\n\nEmpty content received from API."
    except RateLimitError:
         print("Error: OpenAI API rate limit exceeded. Cannot generate README.", file=sys.stderr)
         return "# README Generation Error\n\nAPI rate limit exceeded."
    except APITimeoutError:
         print("Error: OpenAI API request timed out. Cannot generate README.", file=sys.stderr)
         return "# README Generation Error\n\nAPI request timed out."
    except APIError as e:
        print(f"Error: OpenAI API returned an error during README generation: {e}", file=sys.stderr)
        return f"# README Generation Error\n\nOpenAI API error:\n```\n{e}\n```"
    except Exception as e:
        print(f"Error calling OpenAI API for README: {e}", file=sys.stderr)
        return f"# README Generation Error\n\nAn error occurred:\n```\n{e}\n```"

def count_tokens(text: str, encoding_name: str = "o200k_base") -> int:
    """
    Counts the number of tokens in a text string using tiktoken.
    Defaults to "o200k_base" encoding suitable for gpt-4o and other recent models.
    """
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        num_tokens = len(encoding.encode(text))
        return num_tokens
    except Exception as e:
        print(f"Error using tiktoken to count tokens (encoding: {encoding_name}): {e}", file=sys.stderr)
        # Fallback or re-raise, for now return 0 or -1 to indicate error
        return -1 # Or 0, or raise an exception