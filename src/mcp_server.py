"""
MCP Server that exposes GitHub Copilot Spaces as tools.

Tools:
  - list_spaces: List available Copilot Spaces
  - query_space: Send a prompt to a Copilot Space

Resources:
  - spaces://list: Resource exposing available Copilot Spaces

Transport: SSE (for browser/UI clients) or stdio (for VS Code integration)
"""

import asyncio
import json
import logging
import os
import sys

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copilot_client import (
    list_copilot_spaces,
    query_copilot_space,
    close_client as close_http,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Create MCP Server ────────────────────────────────────────

mcp = FastMCP(
    "copilot-spaces-mcp",
    instructions=(
        "MCP server to interact with GitHub Copilot Spaces. "
        "Use list_spaces to discover available spaces, then query_space to chat with them."
    ),
)


# ─── Tools ─────────────────────────────────────────────────────

@mcp.tool()
async def list_spaces() -> str:
    """
    List all available GitHub Copilot Spaces for the authenticated user.
    Returns a JSON array of space objects.
    """
    try:
        spaces = await list_copilot_spaces()
        return json.dumps(spaces, indent=2)
    except Exception as e:
        logger.error(f"list_spaces error: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
async def query_space(
    space_id: str,
    prompt: str,
    conversation_history: str = "[]",
) -> str:
    """
    Send a prompt to a GitHub Copilot Space and get a response.

    Args:
        space_id: The ID of the Copilot Space to query
        prompt: The user's message/prompt
        conversation_history: JSON string of previous messages [{"role":"...","content":"..."}]
    """
    try:
        # Parse conversation history
        try:
            history = json.loads(conversation_history)
        except json.JSONDecodeError:
            history = []

        # Build messages for API
        api_messages = list(history[-20:])  # Last 20 for context
        api_messages.append({"role": "user", "content": prompt})

        # Query Copilot Space
        response = await query_copilot_space(space_id, api_messages)

        # Extract assistant reply
        assistant_content = _extract_response(response)

        return json.dumps({
            "response": assistant_content,
            "spaceId": space_id,
        })

    except Exception as e:
        logger.error(f"query_space error: {e}")
        return json.dumps({"error": str(e)})


# ─── Resources ─────────────────────────────────────────────────

@mcp.resource("spaces://list")
async def spaces_resource() -> str:
    """Resource exposing available Copilot Spaces."""
    spaces = await list_copilot_spaces()
    return json.dumps(spaces, indent=2)


# ─── Helpers ───────────────────────────────────────────────────

def _extract_response(response: dict) -> str:
    """Extract the assistant message content from various API response formats."""
    if "choices" in response and len(response["choices"]) > 0:
        return (
            response["choices"][0]
            .get("message", {})
            .get("content", "")
        )
    elif "message" in response:
        return response["message"].get("content", json.dumps(response))
    else:
        return json.dumps(response)


# ─── Entry Point ───────────────────────────────────────────────

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "sse")
    port = int(os.getenv("MCP_SERVER_PORT", "3001"))

    logger.info(f"Starting MCP Server on transport={transport}, port={port}")

    try:
        if transport == "sse":
            mcp.run(transport="sse", host="0.0.0.0", port=port)
        else:
            mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("MCP Server shutting down...")
    finally:
        asyncio.run(close_http())
