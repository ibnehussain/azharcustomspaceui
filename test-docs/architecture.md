# Architecture Overview

## Components

### API Bridge (`src/api_bridge.py`)
FastAPI server running on port 3002. Exposes REST endpoints consumed by the UI and proxies requests to the GitHub MCP server.

| Endpoint | Method | Description |
|---|---|---|
| `/api/spaces` | GET | List all Copilot Spaces |
| `/api/spaces/{owner}/{name}` | GET | Get space details |
| `/api/spaces/{owner}/{name}/query` | POST | Send a chat message |

### Copilot Client (`src/copilot_client.py`)
- Uses **MCP Python SDK** (`streamablehttp_client` + `ClientSession`) to call `list_copilot_spaces` and `get_copilot_space` tools on the remote GitHub MCP server
- Uses **GitHub Models API** (`models.inference.ai.azure.com`) for chat completions

### MCP Server (`src/mcp_server.py`)
Custom FastMCP server that wraps the client functions as MCP tools. Runs on port 3001.

### UI (`ui/`)
Dark-themed single-page chat interface. Loads spaces in the sidebar, selects a space, and sends messages.

## Data Flow

```
Browser UI
    │
    ▼
FastAPI Bridge (port 3002)
    │
    ├── GET /api/spaces ──────► GitHub MCP Server
    │                           api.githubcopilot.com/mcp/x/copilot_spaces
    │                           tool: list_copilot_spaces
    │
    └── POST .../query ───────► GitHub Models API
                                models.inference.ai.azure.com
                                model: gpt-4o
```

## Auth

All calls use a GitHub PAT (`GITHUB_TOKEN`) with `copilot` scope stored in `.env`.
