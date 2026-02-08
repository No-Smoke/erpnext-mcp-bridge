#!/usr/bin/env python3
"""
ERPNext MCP Bridge - Stdio wrapper for Frappe Assistant Core MCP Server.

Proxies JSON-RPC messages between Claude Desktop (stdin/stdout) and
Frappe Assistant Core's StreamableHTTP MCP endpoint via HTTPS.

Environment variables:
    FRAPPE_SERVER_URL: ERPNext site URL (e.g., https://erp.example.com)
    FRAPPE_API_KEY: Frappe API key
    FRAPPE_API_SECRET: Frappe API secret
    MCP_DEBUG: Set to '1' for debug logging
    MCP_TIMEOUT: Request timeout in seconds (default: 10)

Based on the stdio bridge from Frappe Assistant Core by Paul Clinton.
License: MIT
"""

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

import requests


class ERPNextMCPBridge:
    """Stdio bridge between MCP clients and Frappe Assistant Core."""

    MCP_ENDPOINT = "/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"

    def __init__(self):
        self.server_url = os.environ.get("FRAPPE_SERVER_URL", "").rstrip("/")
        self.api_key = os.environ.get("FRAPPE_API_KEY", "")
        self.api_secret = os.environ.get("FRAPPE_API_SECRET", "")
        self.timeout = int(os.environ.get("MCP_TIMEOUT", "10"))
        self.debug = os.environ.get("MCP_DEBUG", "") == "1"

        if not self.server_url:
            self._fatal("FRAPPE_SERVER_URL environment variable is required")
        if not self.api_key or not self.api_secret:
            self._fatal("FRAPPE_API_KEY and FRAPPE_API_SECRET are required")

        self.headers = {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Content-Type": "application/json",
        }

        self.endpoint_url = f"{self.server_url}{self.MCP_ENDPOINT}"
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.output_lock = threading.Lock()

    def _fatal(self, message: str):
        print(f"FATAL: {message}", file=sys.stderr, flush=True)
        sys.exit(1)

    def _log(self, message: str):
        if self.debug:
            print(f"DEBUG: {message}", file=sys.stderr, flush=True)

    def _log_error(self, message: str):
        print(f"ERROR: {message}", file=sys.stderr, flush=True)

    def _error_response(
        self, code: int, message: str, data: Any = None, req_id: Any = None
    ) -> Dict:
        resp: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
        }
        if data is not None:
            resp["error"]["data"] = data
        if req_id is not None:
            resp["id"] = req_id
        return resp

    def _validate_response(self, response: Any, req_id: Any = None) -> Dict:
        if not isinstance(response, dict):
            return {"jsonrpc": "2.0", "id": req_id, "result": response}
        if "jsonrpc" not in response:
            response["jsonrpc"] = "2.0"
        if req_id is not None and "id" not in response:
            response["id"] = req_id
        if "result" not in response and "error" not in response:
            return {"jsonrpc": "2.0", "id": req_id, "result": response}
        return response

    def _send_to_server(self, request_data: Dict) -> Dict:
        """Forward request to Frappe Assistant Core MCP endpoint."""
        req_id = request_data.get("id")
        try:
            self._log(f">> {request_data.get('method')} (id={req_id})")
            resp = requests.post(
                self.endpoint_url,
                headers=self.headers,
                json=request_data,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                result = resp.json()
                # Frappe wraps responses in {"message": ...}
                if isinstance(result, dict) and "message" in result:
                    return self._validate_response(result["message"], req_id)
                return self._validate_response(result, req_id)
            else:
                self._log_error(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return self._error_response(
                    -32603,
                    f"Server error: {resp.status_code}",
                    resp.text[:500],
                    req_id,
                )
        except requests.exceptions.Timeout:
            self._log_error("Request timed out")
            return self._error_response(-32001, "Request timed out", None, req_id)
        except requests.exceptions.ConnectionError:
            self._log_error(f"Cannot connect to {self.server_url}")
            return self._error_response(
                -32603, "Connection failed", f"Cannot reach {self.server_url}", req_id
            )
        except Exception as e:
            self._log_error(f"Request failed: {e}")
            return self._error_response(-32603, "Internal error", str(e), req_id)

    def _handle_local(self, request: Dict) -> Optional[Dict]:
        """Handle requests that don't need to go to the server."""
        method = request.get("method")
        req_id = request.get("id")

        if method == "initialize":
            resp: Dict[str, Any] = {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}, "prompts": {}},
                    "serverInfo": {"name": "erpnext-fac", "version": "1.0.0"},
                },
            }
            if req_id is not None:
                resp["id"] = req_id
            return resp

        if method == "resources/list":
            resp = {"jsonrpc": "2.0", "result": {"resources": []}}
            if req_id is not None:
                resp["id"] = req_id
            return resp

        return None  # Not handled locally

    def _process_request(self, request: Dict):
        """Process a single JSON-RPC request."""
        try:
            req_id = request.get("id")
            method = request.get("method", "")

            # Try local handling first
            response = self._handle_local(request)
            if response is None:
                # Forward to FAC server
                response = self._send_to_server(request)

            # Only respond if request had an id (not a notification)
            if req_id is not None:
                with self.output_lock:
                    print(json.dumps(response), flush=True)
            else:
                self._log(f"Notification: {method}")

        except Exception as e:
            self._log_error(f"Error: {e}")
            if request.get("id") is not None:
                with self.output_lock:
                    print(
                        json.dumps(
                            self._error_response(
                                -32603, str(e), None, request.get("id")
                            )
                        ),
                        flush=True,
                    )

    def run(self):
        """Main stdio loop."""
        self._log(f"Bridge started -> {self.server_url}")
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    request = json.loads(line)
                    self.executor.submit(self._process_request, request)
                except json.JSONDecodeError as e:
                    self._log_error(f"Invalid JSON: {e}")
                    print(
                        json.dumps(
                            self._error_response(-32700, "Parse error", str(e))
                        ),
                        flush=True,
                    )
        except KeyboardInterrupt:
            self._log("Stopped")
        except Exception as e:
            self._log_error(f"Fatal: {e}")
            sys.exit(1)
        finally:
            self.executor.shutdown(wait=True)


def main():
    bridge = ERPNextMCPBridge()
    bridge.run()


if __name__ == "__main__":
    main()
