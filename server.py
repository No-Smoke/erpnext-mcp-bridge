#!/usr/bin/env python3
"""
ERPNext MCP Bridge Server
Bridges stdio-based MCP (for Claude Desktop) to ERPNext's Frappe Assistant Core HTTP API
"""

import asyncio
import json
import sys
import os
import httpx
from typing import Any

# MCP Protocol constants
JSONRPC_VERSION = "2.0"

class ERPNextBridge:
    def __init__(self):
        self.base_url = os.environ.get("ERPNEXT_URL", "https://erp.ethospower.org")
        self.api_key = os.environ.get("ERPNEXT_API_KEY", "")
        self.api_secret = os.environ.get("ERPNEXT_API_SECRET", "")
        self.mcp_endpoint = f"{self.base_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
        
    def get_auth_header(self) -> dict:
        """Generate authorization header for ERPNext API"""
        return {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Content-Type": "application/json"
        }
    
    async def forward_to_erpnext(self, request: dict) -> dict:
        """Forward MCP request to ERPNext and return response"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.mcp_endpoint,
                    headers=self.get_auth_header(),
                    json=request
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "jsonrpc": JSONRPC_VERSION,
                        "id": request.get("id"),
                        "error": {
                            "code": -32603,
                            "message": f"ERPNext returned status {response.status_code}",
                            "data": response.text[:500]
                        }
                    }
            except Exception as e:
                return {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Connection error: {str(e)}"
                    }
                }

    def handle_initialize(self, request: dict) -> dict:
        """Handle MCP initialize request"""
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "erpnext-mcp-bridge",
                    "version": "1.0.0"
                }
            }
        }

    async def handle_request(self, request: dict) -> dict:
        """Route MCP request to appropriate handler"""
        method = request.get("method", "")
        
        # Handle local protocol methods
        if method == "initialize":
            return self.handle_initialize(request)
        elif method == "notifications/initialized":
            return None  # No response needed for notifications
        
        # Forward everything else to ERPNext
        return await self.forward_to_erpnext(request)


async def main():
    """Main stdio loop for MCP communication"""
    bridge = ERPNextBridge()
    
    # Check configuration
    if not bridge.api_key or not bridge.api_secret:
        sys.stderr.write("ERROR: ERPNEXT_API_KEY and ERPNEXT_API_SECRET must be set\n")
        sys.exit(1)
    
    sys.stderr.write(f"ERPNext MCP Bridge started, connecting to {bridge.base_url}\n")
    
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
    
    while True:
        try:
            # Read line from stdin
            line = await reader.readline()
            if not line:
                break
            
            line = line.decode('utf-8').strip()
            if not line:
                continue
            
            # Parse JSON-RPC request
            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                sys.stderr.write(f"JSON parse error: {e}\n")
                continue
            
            # Handle request
            response = await bridge.handle_request(request)
            
            # Send response (if any)
            if response:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
