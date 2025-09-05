import os
from pathlib import Path


def collect_files_in_folder(folder_path: str, tree: dict) -> list[str]:
    """
    Recursively collect all file paths within a folder from the tree structure.
    
    Args:
        folder_path: The path of the folder to collect files from (e.g., 'src/codesum')
        tree: The tree structure dictionary
        
    Returns:
        List of absolute file paths within the folder
    """
    # Navigate to the folder in the tree
    parts = folder_path.split('/')
    current_level = tree
    
    # Navigate through the tree to find the folder
    for part in parts:
        if part and part in current_level:
            current_level = current_level[part]
        else:
            # Folder not found in tree
            return []
    
    # Collect all files recursively from this point
    file_paths = []
    _collect_files_recursive(current_level, file_paths)
    return file_paths


def _collect_files_recursive(tree_node: dict, file_paths: list[str]):
    """Helper function to recursively collect file paths."""
    for key, value in tree_node.items():
        if isinstance(value, dict):
            # This is a subdirectory, recurse into it
            _collect_files_recursive(value, file_paths)
        else:
            # This is a file, add its path
            file_paths.append(value)  # value is the absolute path string