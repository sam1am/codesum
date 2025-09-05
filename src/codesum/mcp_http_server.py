"""HTTP server for CodeSum MCP."""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .mcp_server import CodeSumMCPServer


class CodeSumMCPHandler(BaseHTTPRequestHandler):
    """HTTP handler for CodeSum MCP requests."""
    
    def do_POST(self):
        """Handle POST requests."""
        # Parse URL
        parsed_path = urlparse(self.path)
        
        # Only handle /summarize endpoint
        if parsed_path.path != '/summarize':
            self.send_error(404, "Endpoint not found")
            return
        
        # Get content length
        content_length = int(self.headers.get('Content-Length', 0))
        
        # Read request body
        post_data = self.rfile.read(content_length)
        
        try:
            # Parse JSON
            request_data = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        
        # Create MCP server
        base_dir = Path(os.getcwd())
        mcp_server = CodeSumMCPServer(base_dir)
        
        # Process request
        result = mcp_server.process_request(request_data)
        
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests."""
        # Parse URL
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        
        # Health check endpoint
        if parsed_path.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {'status': 'ok', 'service': 'codesum-mcp'}
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return
        
        # Summarize endpoint with query parameters
        if parsed_path.path == '/summarize':
            # Extract query and max_files from query params
            query = query_params.get('query', [''])[0]
            max_files = int(query_params.get('max_files', [10])[0])
            
            if not query:
                self.send_error(400, "Query parameter is required")
                return
            
            # Create MCP server
            base_dir = Path(os.getcwd())
            mcp_server = CodeSumMCPServer(base_dir)
            
            # Process request
            result = mcp_server.process_request({
                'query': query,
                'max_files': max_files
            })
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
            return
        
        # Serve documentation
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        doc_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>CodeSum MCP Server</title>
        </head>
        <body>
            <h1>CodeSum MCP Server</h1>
            <p>This is the CodeSum MCP (Model Context Protocol) server.</p>
            
            <h2>Endpoints</h2>
            <ul>
                <li><code>GET /health</code> - Health check</li>
                <li><code>GET /summarize?query=&lt;query&gt;&amp;max_files=&lt;N&gt;</code> - Generate summary with query params</li>
                <li><code>POST /summarize</code> - Generate summary with JSON body</li>
            </ul>
            
            <h2>POST /summarize</h2>
            <p>Accepts a JSON body with:</p>
            <ul>
                <li><code>query</code> (required) - The query to match against files</li>
                <li><code>max_files</code> (optional, default 10) - Maximum number of files to include</li>
            </ul>
            
            <h3>Example Request</h3>
            <pre>
{
  "query": "Find files related to configuration",
  "max_files": 5
}
            </pre>
        </body>
        </html>
        """
        self.wfile.write(doc_html.encode('utf-8'))


def run_mcp_server(host='localhost', port=8000):
    """Run the MCP server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, CodeSumMCPHandler)
    print(f"Starting CodeSum MCP server on {host}:{port}...")
    httpd.serve_forever()


if __name__ == "__main__":
    run_mcp_server()