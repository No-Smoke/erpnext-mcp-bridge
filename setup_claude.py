#!/usr/bin/env python3
"""
Setup script for configuring Claude Desktop to use ERPNext MCP Bridge.

Run: python setup_claude.py

This will:
1. Prompt for your ERPNext site URL and API credentials
2. Test the connection
3. Update your Claude Desktop config
"""

import json
import os
import shutil
import sys
from pathlib import Path


def get_config_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "linux":
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    else:
        print(f"Unsupported platform: {sys.platform}")
        sys.exit(1)


def find_bridge_command() -> str:
    """Find the erpnext-mcp-bridge executable."""
    result = shutil.which("erpnext-mcp-bridge")
    if result:
        return result
    # Try common locations
    for path in [
        Path.home() / ".local" / "bin" / "erpnext-mcp-bridge",
        Path(sys.prefix) / "bin" / "erpnext-mcp-bridge",
    ]:
        if path.exists():
            return str(path)
    return "erpnext-mcp-bridge"


def test_connection(url: str, key: str, secret: str) -> bool:
    """Test API connection."""
    try:
        import requests
        resp = requests.get(
            f"{url}/api/method/frappe.auth.get_logged_user",
            headers={"Authorization": f"token {key}:{secret}"},
            timeout=10,
        )
        if resp.status_code == 200:
            user = resp.json().get("message", "unknown")
            print(f"  Connected as: {user}")
            return True
        else:
            print(f"  Connection failed: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  Connection error: {e}")
        return False


def test_mcp(url: str, key: str, secret: str) -> bool:
    """Test MCP endpoint."""
    try:
        import requests
        resp = requests.post(
            f"{url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
            headers={"Authorization": f"token {key}:{secret}", "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1, "params": {}},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Unwrap Frappe envelope
            if isinstance(data, dict) and "message" in data:
                data = data["message"]
            tools = data.get("result", {}).get("tools", [])
            print(f"  MCP endpoint OK: {len(tools)} tools available")
            for t in tools:
                print(f"    - {t['name']}")
            return True
        else:
            print(f"  MCP endpoint failed: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  MCP test error: {e}")
        return False


def main():
    print("ERPNext MCP Bridge - Claude Desktop Setup")
    print("=" * 45)
    print()

    url = input("ERPNext site URL (e.g., https://erp.example.com): ").strip().rstrip("/")
    key = input("API Key: ").strip()
    secret = input("API Secret: ").strip()
    server_name = input("Server name in config [erpnext-fac]: ").strip() or "erpnext-fac"

    print("\nTesting connection...")
    if not test_connection(url, key, secret):
        if input("Continue anyway? [y/N]: ").lower() != "y":
            sys.exit(1)

    print("Testing MCP endpoint...")
    test_mcp(url, key, secret)

    config_path = get_config_path()
    bridge_cmd = find_bridge_command()

    print(f"\nConfig file: {config_path}")
    print(f"Bridge command: {bridge_cmd}")

    # Load or create config
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            print("Warning: existing config is invalid JSON, creating new")

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Add/update server entry
    config["mcpServers"][server_name] = {
        "command": bridge_cmd,
        "args": [],
        "env": {
            "FRAPPE_SERVER_URL": url,
            "FRAPPE_API_KEY": key,
            "FRAPPE_API_SECRET": secret,
        },
    }

    # Backup and write
    if config_path.exists():
        backup = config_path.with_suffix(".json.bak")
        shutil.copy2(config_path, backup)
        print(f"Backup: {backup}")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))
    print(f"\n✅ Configuration saved to {config_path}")
    print("\nRestart Claude Desktop to connect to ERPNext.")


if __name__ == "__main__":
    main()
