# ERPNext MCP Bridge

A stdio bridge that connects **Claude Desktop** (or any MCP client) to **Frappe Assistant Core** running on your ERPNext instance.

This enables Claude to directly create, read, update, and delete ERPNext documents, run reports, execute workflows, and search across your ERP — all through native MCP tool calls.

## Prerequisites

- Python 3.10+
- [Frappe Assistant Core](https://github.com/buildswithpaul/Frappe_Assistant_Core) installed on your ERPNext site
- ERPNext API key with Administrator or System Manager role

## Quick Install

```bash
# Clone and install
git clone https://github.com/No-Smoke/erpnext-mcp-bridge.git
cd erpnext-mcp-bridge
pip install -e .

# Or install directly
pip install git+https://github.com/No-Smoke/erpnext-mcp-bridge.git
```

## Setup

Run the setup script to configure Claude Desktop automatically:

```bash
python setup_claude.py
```

Or manually add to `~/.config/Claude/claude_desktop_config.json` (Linux) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "erpnext-fac": {
      "command": "erpnext-mcp-bridge",
      "args": [],
      "env": {
        "FRAPPE_SERVER_URL": "https://your-site.example.com",
        "FRAPPE_API_KEY": "your-api-key",
        "FRAPPE_API_SECRET": "your-api-secret"
      }
    }
  }
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FRAPPE_SERVER_URL` | Yes | Your ERPNext site URL (e.g., `https://erp.example.com`) |
| `FRAPPE_API_KEY` | Yes | API key from User Settings in ERPNext |
| `FRAPPE_API_SECRET` | Yes | API secret (generated when creating API key) |
| `MCP_DEBUG` | No | Set to `1` for debug logging to stderr |

## Available Tools (16)

Once connected, Claude gets access to these ERPNext tools:

| Tool | Description |
|------|-------------|
| `create_document` | Create new documents with validation and child table support |
| `get_document` | Retrieve document details |
| `update_document` | Modify existing documents |
| `delete_document` | Delete documents |
| `list_documents` | Search and filter document lists |
| `submit_document` | Submit draft documents |
| `search_documents` | Global search across all DocTypes |
| `search_doctype` | Search within a specific DocType |
| `search_link` | Search link field options |
| `search` | Vector search (if configured) |
| `fetch` | Retrieve complete document by ID |
| `get_doctype_info` | Get DocType metadata and field info |
| `generate_report` | Execute business reports |
| `report_list` | Discover available reports |
| `report_requirements` | Get report filter requirements |
| `run_workflow` | Execute workflow actions (approve, reject, etc.) |

## How It Works

```
Claude Desktop <--stdio--> erpnext-mcp-bridge <--HTTPS--> Frappe Assistant Core (ERPNext)
```

The bridge:
1. Reads JSON-RPC messages from stdin (Claude Desktop)
2. Forwards them via HTTPS to the FAC MCP endpoint on your ERPNext
3. Unwraps Frappe's response envelope
4. Returns the JSON-RPC response on stdout

Authentication uses Frappe's standard API key/secret token auth.

## Generating API Keys

1. Log into ERPNext as Administrator
2. Go to **User Settings** > **API Access**
3. Click **Generate Keys**
4. Save the API Secret (shown only once)
5. The API Key is always visible in User Settings

For admin-level access, generate keys on the Administrator user account.

## Troubleshooting

**"Connection failed"**: Verify your `FRAPPE_SERVER_URL` is accessible and Frappe Assistant Core is installed.

**"Not whitelisted"**: The API key user needs Administrator or System Manager role.

**Timeout errors**: The bridge uses a 5-second timeout per request. For large operations, this may need adjusting.

**Debug mode**: Set `MCP_DEBUG=1` in the env to see request/response details on stderr.

## License

MIT

## Credits

Based on the stdio bridge from [Frappe Assistant Core](https://github.com/buildswithpaul/Frappe_Assistant_Core) by Paul Clinton.
