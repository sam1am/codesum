"""MCP Server for CodeSum - AI-powered code summarization tool."""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from openai import OpenAI

from . import config
from . import file_utils
from . import openai_utils
from . import summary_utils


class CodeSumMCPServer:
    """MCP Server implementation for CodeSum."""
    
    def __init__(self, base_dir: Path = Path('.')):
        """Initialize the MCP server."""
        self.base_dir = base_dir.resolve()
        self.api_key, self.llm_model = config.load_config()
        self.openai_client = None
        
        if self.api_key:
            try:
                self.openai_client = OpenAI(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Could not initialize OpenAI client: {e}")
    
    def select_relevant_files(self, query: str, max_files: int = 10) -> List[str]:
        """
        Use LLM to select the most relevant files based on a query.
        
        Args:
            query: The query to match against files
            max_files: Maximum number of files to return
            
        Returns:
            List of absolute file paths
        """
        # Build the file tree
        gitignore_specs = file_utils.parse_gitignore(self.base_dir)
        ignore_list = file_utils.DEFAULT_IGNORE_LIST
        
        # Add custom ignore patterns
        custom_ignore_file = summary_utils.get_summary_dir(self.base_dir) / summary_utils.CUSTOM_IGNORE_FILENAME
        if custom_ignore_file.exists():
            try:
                with open(custom_ignore_file, "r", encoding='utf-8') as f:
                    custom_ignores = [line.strip() for line in f.read().splitlines() 
                                    if line.strip() and not line.strip().startswith('#')]
                    ignore_list.extend(custom_ignores)
            except Exception as e:
                print(f"Warning: Could not read custom ignore file {custom_ignore_file}: {e}")
        
        tree = file_utils.build_tree_with_folders(self.base_dir, gitignore_specs, ignore_list)
        flattened_items = file_utils.flatten_tree(tree)
        
        # Get file paths
        file_paths = [item[1] for item in flattened_items]  # item[1] is the full path
        
        # If we have an OpenAI client, use it to rank files
        if self.openai_client and file_paths:
            ranked_files = self._rank_files_with_llm(query, file_paths)
            return ranked_files[:max_files]
        
        # Fallback: return first N files
        return file_paths[:max_files]
    
    def _rank_files_with_llm(self, query: str, file_paths: List[str]) -> List[str]:
        """
        Use LLM to rank files by relevance to query.
        
        Args:
            query: The query to match against files
            file_paths: List of file paths to rank
            
        Returns:
            List of file paths ranked by relevance
        """
        # Create a prompt for the LLM to rank files
        file_info_list = []
        for path_str in file_paths:
            try:
                path_obj = Path(path_str)
                relative_path = path_obj.relative_to(self.base_dir)
                # Get first few lines of the file for context
                with open(path_obj, 'r', encoding='utf-8') as f:
                    content_preview = f.read(500)  # First 500 chars
                file_info_list.append({
                    "path": str(relative_path),
                    "preview": content_preview
                })
            except Exception:
                # Skip files that can't be read
                continue
        
        if not file_info_list:
            return file_paths
            
        prompt = f"""
        I have a codebase with the following files. Please rank them by relevance to this query: "{query}"
        
        Files:
        {json.dumps(file_info_list, indent=2)}
        
        Return ONLY a JSON array of file paths, ordered from most to least relevant.
        Example: ["src/main.py", "src/utils.py", "README.md"]
        """
        
        try:
            completion = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a code analysis assistant that ranks files by relevance to a query."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.1
            )
            
            response_content = completion.choices[0].message.content
            # Extract JSON from response
            start_idx = response_content.find('[')
            end_idx = response_content.rfind(']') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_content[start_idx:end_idx]
                ranked_paths = json.loads(json_str)
                
                # Convert back to absolute paths and filter valid ones
                result_paths = []
                for rel_path in ranked_paths:
                    abs_path = self.base_dir / rel_path
                    if str(abs_path) in file_paths:
                        result_paths.append(str(abs_path))
                
                # Add any files that weren't in the LLM response
                for path in file_paths:
                    if path not in result_paths:
                        result_paths.append(path)
                
                return result_paths
            else:
                # Fallback if JSON parsing fails
                return file_paths
                
        except Exception as e:
            print(f"Warning: Could not rank files with LLM: {e}")
            return file_paths
    
    def generate_summary(self, query: str, max_files: int = 10) -> str:
        """
        Generate a code summary based on a query.
        
        Args:
            query: The query to generate summary for
            max_files: Maximum number of files to include in summary
            
        Returns:
            Summary content as string
        """
        # Select relevant files
        selected_files = self.select_relevant_files(query, max_files)
        
        if not selected_files:
            return "No relevant files found for the query."
        
        # Create a summary
        project_root = self.base_dir
        gitignore_specs = file_utils.parse_gitignore(project_root)
        tree_output = file_utils.get_tree_output(project_root, gitignore_specs, file_utils.DEFAULT_IGNORE_LIST)
        
        summary_content = []
        summary_content.append(f"# Code Summary for Query: {query}")
        summary_content.append(f"Project Root: {project_root}")
        summary_content.append(f"Project Structure:")
        summary_content.append(f"```\n{tree_output}\n```")
        summary_content.append("---")
        
        # Add content from each selected file
        for file_path_str in selected_files:
            try:
                file_path_obj = Path(file_path_str)
                relative_path = file_path_obj.relative_to(project_root)
                lang_hint = file_path_obj.suffix.lstrip('.') if file_path_obj.suffix else ""
                
                summary_content.append(f"## File: {relative_path.as_posix()}")
                summary_content.append(f"```{lang_hint}")
                
                with open(file_path_obj, "r", encoding='utf-8') as f:
                    summary_content.append(f.read())
                    
                summary_content.append("```")
                summary_content.append("---")
            except Exception as e:
                summary_content.append(f"## File: {file_path_str}")
                summary_content.append(f"Error reading file: {e}")
                summary_content.append("---")
        
        return "\n".join(summary_content)
    
    def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an MCP request.
        
        Args:
            request_data: Request data with 'query' and optional 'max_files'
            
        Returns:
            Response dictionary with 'summary' and 'selected_files'
        """
        query = request_data.get('query', '')
        max_files = request_data.get('max_files', 10)
        
        if not query:
            return {
                'error': 'Query is required',
                'summary': '',
                'selected_files': []
            }
        
        # Generate summary
        summary = self.generate_summary(query, max_files)
        selected_files = self.select_relevant_files(query, max_files)
        
        return {
            'summary': summary,
            'selected_files': selected_files
        }


def create_mcp_server(base_dir: Path = Path('.')) -> CodeSumMCPServer:
    """Factory function to create an MCP server instance."""
    return CodeSumMCPServer()


# For testing
if __name__ == "__main__":
    server = CodeSumMCPServer()
    result = server.process_request({
        'query': 'Find files related to configuration',
        'max_files': 5
    })
    print(json.dumps(result, indent=2))