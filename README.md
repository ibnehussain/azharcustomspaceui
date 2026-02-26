# Copilot Spaces Chat — Custom UI via MCP

A **Python / FastAPI** custom web UI for chatting with your **GitHub Copilot Spaces** using the official [GitHub Remote MCP Server](https://github.com/github/github-mcp-server).

- Lists your Copilot Spaces via the MCP `list_copilot_spaces` tool
- Fetches each space's linked repository files and injects them as live context
- Sends chat messages through the **GitHub Models API** (`gpt-4o`)
- Maintains per-conversation history in memory
- Dark-themed single-page chat UI, no external database required

## Architecture

```
Browser UI  (ui/)
    │
    ▼
FastAPI Bridge  src/api_bridge.py   (port 3002)
    │
    ├── GET /api/spaces ──────────► GitHub Remote MCP Server
    │   GET /api/spaces/:owner/:name   api.githubcopilot.com/mcp/x/copilot_spaces
    │                                  tools: list_copilot_spaces / get_copilot_space
    │
    └── POST /api/spaces/:owner/:name/query
                     │
                     └──────────────► GitHub Models API
                                      models.inference.ai.azure.com
                                      model: gpt-4o
```

## Project Structure

```
.
├── src/
│   ├── api_bridge.py      # FastAPI REST bridge + static file server
│   ├── copilot_client.py  # MCP client (spaces) + GitHub Models chat
│   ├── mcp_server.py      # Optional FastMCP server wrapping client tools
│   └── models.py          # Pydantic request/response models
├── ui/
│   ├── index.html         # Chat UI shell
│   ├── app.js             # Space selector, chat, conversation history
│   └── style.css          # Dark theme styles
├── .env.example           # Environment variable template
├── requirements.txt
└── .vscode/
    └── mcp.json           # VS Code MCP server config
```

## Prerequisites

- Python 3.11+
- GitHub Personal Access Token with **`copilot`** scope — [create one](https://github.com/settings/tokens)
- At least one [Copilot Space](https://github.com/copilot/spaces) linked to a GitHub repository

## Quick Start

```bash
# 1. Clone
git clone https://github.com/ibnehussain/azharcustomspaceui.git
cd azharcustomspaceui

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
# Edit .env and set GITHUB_TOKEN

# 5. Start the server
python src/api_bridge.py
```

Open **http://localhost:3002** in your browser.

## How Space Context Works

When you start a new conversation the bridge calls `get_copilot_space` via MCP. Every file from the linked repository is fetched and injected into the system prompt, so the AI answers questions grounded in your actual knowledge files.

> **Tip:** For the AI to answer file-specific questions, link a GitHub repository to your Copilot Space at [github.com/copilot/spaces](https://github.com/copilot/spaces) → Add knowledge → GitHub Repository.

## VS Code MCP Integration

The `.vscode/mcp.json` configures three servers:

| Server | URL | Purpose |
|--------|-----|---------|
| `github-copilot-spaces` | `api.githubcopilot.com/mcp/x/copilot_spaces` | Copilot Spaces toolset |
| `github-all` | `api.githubcopilot.com/mcp/` | All GitHub MCP tools |
| `copilot-spaces-local` | stdio | Local FastMCP wrapper |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/spaces` | List all Copilot Spaces |
| GET | `/api/spaces/{owner}/{name}` | Get space details + files |
| POST | `/api/spaces/{owner}/{name}/query` | Send a chat message |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | ✅ | GitHub PAT with `copilot` scope |
| `MCP_SERVER_PORT` | No (default: 3001) | Port for the optional local MCP server |
| `API_BRIDGE_PORT` | No (default: 3002) | Port for the FastAPI bridge |

## License

MIT

