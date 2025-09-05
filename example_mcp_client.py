#!/usr/bin/env python3
"""Example client for the CodeSum MCP server."""

import json
import requests
import sys

def main():
    """Example of using the CodeSum MCP server."""
    # Server configuration
    server_url = "http://localhost:8000"
    
    # Example query
    query = "Find files related to configuration"
    max_files = 5
    
    # Method 1: Using GET request with query parameters
    print("Method 1: GET request with query parameters")
    try:
        response = requests.get(
            f"{server_url}/summarize",
            params={"query": query, "max_files": max_files}
        )
        if response.status_code == 200:
            result = response.json()
            print(f"Summary length: {len(result.get('summary', ''))} characters")
            print(f"Selected files: {len(result.get('selected_files', []))} files")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error making request: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Method 2: Using POST request with JSON body
    print("Method 2: POST request with JSON body")
    try:
        response = requests.post(
            f"{server_url}/summarize",
            json={
                "query": query,
                "max_files": max_files
            },
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            result = response.json()
            print(f"Summary length: {len(result.get('summary', ''))} characters")
            print(f"Selected files: {len(result.get('selected_files', []))} files")
            
            # Save summary to file
            with open("mcp_summary.md", "w") as f:
                f.write(result.get('summary', ''))
            print("Summary saved to mcp_summary.md")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error making request: {e}")

if __name__ == "__main__":
    main()