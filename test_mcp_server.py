#!/usr/bin/env python3
"""Test script for the CodeSum MCP server."""

import json
import sys
from pathlib import Path

# Add the src directory to the path so we can import codesum
sys.path.insert(0, str(Path(__file__).parent / "src"))

from codesum.mcp_server import CodeSumMCPServer


def test_mcp_server():
    """Test the MCP server functionality."""
    # Create server instance
    server = CodeSumMCPServer()
    
    # Test processing a request
    result = server.process_request({
        'query': 'Find files related to configuration',
        'max_files': 5
    })
    
    print("MCP Server Test Results:")
    print("========================")
    print(f"Summary length: {len(result.get('summary', ''))} characters")
    print(f"Selected files: {len(result.get('selected_files', []))} files")
    print("\nSelected files:")
    for file_path in result.get('selected_files', [])[:3]:  # Show first 3
        print(f"  - {file_path}")
    
    # Check for errors
    if 'error' in result:
        print(f"\nError: {result['error']}")
        return False
    
    print("\nTest completed successfully!")
    return True


if __name__ == "__main__":
    test_mcp_server()