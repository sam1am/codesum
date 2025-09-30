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


def find_parent_folder_path(file_path: str, options: list) -> str | None:
    """
    Find the parent folder path of a file from the options list.

    Args:
        file_path: The path string of the file (e.g., 'src/codesum/tui.py')
        options: The list of tuples (display_name, path, is_folder, full_path)

    Returns:
        The parent folder path if found, otherwise None
    """
    # Extract the directory part from the file path
    if '/' not in file_path:
        return None  # File is at root, no parent folder

    parent_path = '/'.join(file_path.split('/')[:-1])

    # Look for this parent path in the options list
    for display_name, path, is_folder, full_path in options:
        if is_folder and path == parent_path:
            return path

    # If not found, try progressively shorter parent paths
    while '/' in parent_path:
        for display_name, path, is_folder, full_path in options:
            if is_folder and path == parent_path:
                return path
        parent_path = '/'.join(parent_path.split('/')[:-1])

    return None


def collect_all_subfolders(folder_path: str, tree: dict) -> list[str]:
    """
    Recursively collect all subfolder paths within a folder from the tree structure.

    Args:
        folder_path: The path of the folder to collect subfolders from (e.g., 'src/codesum')
        tree: The tree structure dictionary

    Returns:
        List of folder paths (including the root folder_path itself)
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

    # Collect all subfolders recursively from this point
    folder_paths = [folder_path]  # Include the root folder itself
    _collect_subfolders_recursive(current_level, folder_path, folder_paths)
    return folder_paths


def _collect_subfolders_recursive(tree_node: dict, current_path: str, folder_paths: list[str]):
    """Helper function to recursively collect subfolder paths."""
    for key, value in tree_node.items():
        if isinstance(value, dict):
            # This is a subdirectory
            subfolder_path = f"{current_path}/{key}"
            folder_paths.append(subfolder_path)
            # Recurse into it
            _collect_subfolders_recursive(value, subfolder_path, folder_paths)