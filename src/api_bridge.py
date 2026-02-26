"""
FastAPI REST API bridge — serves the custom UI and provides HTTP endpoints
that proxy to the GitHub Copilot Spaces API.

Endpoints:
  GET  /api/spaces                  — List Copilot Spaces
  GET  /api/spaces/{space_id}       — Get space details
  POST /api/spaces/{space_id}/query — Query a Copilot Space
  GET  /                            — Serve the UI
"""

import os
import sys
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copilot_client import (
    list_copilot_spaces,
    query_copilot_space,
    get_copilot_space,
    close_client as close_http,
)
from models import QueryRequest

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─── In-memory conversation store (per server session) ─────────

# Key: conversationId, Value: list of {"role": ..., "content": ...}
_conversations: dict[str, list[dict]] = {}
_conv_counter = 0


def _new_conversation_id() -> str:
    global _conv_counter
    _conv_counter += 1
    return f"conv-{_conv_counter}"


# ─── App Lifecycle ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("API Bridge starting up...")
    yield
    logger.info("API Bridge shutting down...")
    await close_http()


app = FastAPI(
    title="Copilot Spaces MCP Bridge",
    description="REST API bridge for GitHub Copilot Spaces via MCP",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Copilot Spaces Endpoints ─────────────────────────────────

@app.get("/api/spaces")
async def api_list_spaces():
    """List all available Copilot Spaces."""
    try:
        spaces = await list_copilot_spaces()
        return spaces
    except Exception as e:
        logger.error(f"Error listing spaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/spaces/{owner}/{name}")
async def api_get_space(owner: str, name: str):
    """Get details of a specific Copilot Space."""
    space_ref = f"{owner}/{name}"
    try:
        space = await get_copilot_space(space_ref)
        return space
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/spaces/{owner}/{name}/query")
async def api_query_space(owner: str, name: str, request: QueryRequest):
    """Send a prompt to a Copilot Space with in-memory conversation context."""
    space_ref = f"{owner}/{name}"
    try:
        # Get or create conversation history
        conv_id = request.conversationId
        if conv_id and conv_id in _conversations:
            history = _conversations[conv_id]
        else:
            conv_id = _new_conversation_id()
            # Fetch live space context (files) to ground the assistant
            try:
                space_detail = await get_copilot_space(space_ref)
                file_context = space_detail.get("context", "")
            except Exception:
                file_context = ""

            system_content = (
                f"You are GitHub Copilot operating in the '{name}' space "
                f"(owner: {owner}). "
                "Answer questions using ONLY the knowledge files below. "
                "If the answer is not in the files, say so honestly.\n\n"
            )
            if file_context:
                system_content += f"## Space Knowledge Files\n\n{file_context}"
            else:
                system_content += "(No knowledge files are attached to this space yet.)"

            history = [{"role": "system", "content": system_content}]
            _conversations[conv_id] = history

        # Add user message
        history.append({"role": "user", "content": request.prompt})

        # Build API messages (last 20 for context window)
        api_messages = history[-20:]

        # Call Copilot Space
        response = await query_copilot_space(space_ref, api_messages)

        # Extract assistant reply
        assistant_content = _extract_response(response)

        # Store assistant reply in history
        history.append({"role": "assistant", "content": assistant_content})

        return {
            "conversationId": conv_id,
            "response": assistant_content,
            "spaceId": space_ref,
        }

    except Exception as e:
        logger.error(f"Error querying space {owner}/{name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# ─── Serve Static UI Files ────────────────────────────────────

UI_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui"
)

if os.path.exists(UI_DIR):
    app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

    @app.get("/")
    async def serve_ui():
        """Serve the custom UI."""
        return FileResponse(os.path.join(UI_DIR, "index.html"))


# ─── Entry Point ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_BRIDGE_PORT", "3002"))
    logger.info(f"Starting API Bridge on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
