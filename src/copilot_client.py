"""GitHub Copilot Spaces client — powered by the Remote GitHub MCP Server.

Calls GitHub's official MCP server at https://api.githubcopilot.com/mcp/
via the MCP Python SDK client to access the 'copilot_spaces' toolset.

For chat queries, uses the GitHub Models inference API (accepts PATs directly).
"""

import os
import json
import logging
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Remote GitHub MCP Server — dedicated copilot_spaces toolset URL
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/x/copilot_spaces"
# GitHub Models inference API — accepts GitHub PATs, OpenAI-compatible
GITHUB_CHAT_URL = "https://models.inference.ai.azure.com/chat/completions"
# Default model for GitHub Models API
GITHUB_CHAT_MODEL = "gpt-4o"


def _get_token() -> str:
    """Return the GitHub PAT from environment."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError(
            "GITHUB_TOKEN environment variable is not set. "
            "Create a GitHub PAT with 'copilot' scope."
        )
    return token


def _mcp_headers() -> dict:
    """Authorization header for the remote GitHub MCP server."""
    return {
        "Authorization": f"Bearer {_get_token()}",
    }


def _parse_mcp_result(result) -> any:
    """Parse MCP tool-call result into a Python object.

    GitHub's MCP server returns results as 'resource' content items:
      content[0] = { type: 'resource', resource: { uri: ..., mimeType: ..., text: '...' } }
    Falls back to 'text' content items for other servers.
    """
    if not result or not result.content:
        logger.warning(f"MCP result has no content. result={result}")
        return None

    content_item = result.content[0]
    content_type = getattr(content_item, "type", None)

    # Resource content (GitHub MCP server returns this)
    if content_type == "resource" or hasattr(content_item, "resource"):
        resource = getattr(content_item, "resource", None)
        if resource is None:
            logger.warning(f"Resource content item has no 'resource': {content_item}")
            return None
        text = getattr(resource, "text", None)
        if text is None:
            logger.warning(f"Resource has no 'text': {resource}")
            return None
        logger.debug(f"Resource text (first 500): {text[:500]}")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    # Text content (fallback for other MCP servers)
    text = getattr(content_item, "text", None)
    if text is None:
        logger.warning(f"Content item has no 'text': {content_item} (type={content_type})")
        return None
    logger.debug(f"Text content (first 500): {text[:500]}")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


async def list_copilot_spaces() -> list[dict]:
    """
    List all Copilot Spaces for the authenticated user.

    Calls the `list_copilot_spaces` tool on the Remote GitHub MCP Server.
    The result is captured before any stream-cleanup exceptions propagate.
    """
    spaces_result: list[dict] = []

    try:
        async with streamablehttp_client(
            GITHUB_MCP_URL,
            headers=_mcp_headers(),
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("list_copilot_spaces", {})
                data = _parse_mcp_result(result)

                if isinstance(data, list):
                    spaces_result = data
                elif isinstance(data, dict):
                    spaces_result = data.get("spaces", data.get("items", []))
                else:
                    logger.warning(f"Unexpected spaces response type: {type(data)}")

                # Normalise: add composite 'space_ref' = 'owner/name'
                for space in spaces_result:
                    if isinstance(space, dict):
                        # GitHub MCP returns 'owner_login'; also handle nested {'login': ...}
                        owner = space.get("owner_login") or space.get("owner", "")
                        if isinstance(owner, dict):
                            owner = owner.get("login", "")
                        name = space.get("name", "")
                        space["space_ref"] = f"{owner}/{name}" if owner else name

    except Exception as e:
        # The tool result is received BEFORE the streamable-HTTP GET-stream
        # cleanup fires (returns 405 / 502 on github's server), which raises
        # an ExceptionGroup.  If we already populated spaces_result we win.
        if spaces_result:
            logger.warning(f"MCP stream cleanup warning (data received OK): {e}")
            logger.info(f"Found {len(spaces_result)} Copilot Space(s) (with cleanup warning)")
            return spaces_result
        logger.error(f"Error listing Copilot Spaces via MCP: {e}")
        raise

    logger.info(f"Found {len(spaces_result)} Copilot Space(s)")
    return spaces_result


async def get_copilot_space(space_ref: str) -> dict:
    """
    Get details of a specific Copilot Space including all file contents.

    Returns a dict with:
      - name, owner, space_ref
      - files: list of {uri, content} for every file in the space
      - context: all file contents concatenated as a single string for injection
                 into the system prompt

    Args:
        space_ref: 'owner/name' string (e.g. 'ibnehussain/my-space').
    """
    if "/" in space_ref:
        owner, name = space_ref.split("/", 1)
    else:
        owner = ""
        name = space_ref

    space_result: dict = {}

    try:
        async with streamablehttp_client(
            GITHUB_MCP_URL,
            headers=_mcp_headers(),
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "get_copilot_space",
                    {"owner": owner, "name": name},
                )

                # result.content is a list of EmbeddedResource items.
                # Each has resource.uri and resource.text.
                # URIs look like:
                #   space://<owner>/<id>/contents/name  → space name
                #   space://<owner>/<id>/files/<path>   → file content
                files = []
                space_name = name
                for item in (result.content or []):
                    resource = getattr(item, "resource", None)
                    if resource is None:
                        continue
                    uri = str(getattr(resource, "uri", ""))
                    text = getattr(resource, "text", "") or ""
                    if "/contents/name" in uri:
                        space_name = text.strip() or name
                    elif "/files/" in uri:
                        # Extract readable path after /files/
                        file_path = uri.split("/files/", 1)[-1]
                        if text.strip():  # skip empty files
                            files.append({"path": file_path, "content": text})

                # Build a single context string from all files
                context_parts = []
                for f in files:
                    context_parts.append(
                        f"### File: {f['path']}\n\n{f['content']}"
                    )
                context = "\n\n---\n\n".join(context_parts)

                space_result = {
                    "name": space_name,
                    "owner": owner,
                    "space_ref": space_ref,
                    "files": files,
                    "context": context,
                }
                logger.info(
                    f"Loaded space '{space_ref}': {len(files)} file(s), "
                    f"{len(context)} chars of context"
                )

    except Exception as e:
        if space_result:
            logger.warning(f"MCP stream cleanup warning (data received OK): {e}")
            return space_result
        logger.error(f"Error getting Copilot Space '{space_ref}': {e}")
        raise

    return space_result


async def query_copilot_space(
    space_id: str,
    messages: list[dict],
) -> dict:
    """
    Chat with GitHub Copilot using the Copilot Chat completions API.

    Optionally prepends space context as a system message if the first
    message is not already a system message.

    Args:
        space_id: The 'owner/name' space reference (for logging/context)
        messages: Conversation history list of {'role', 'content'} dicts

    Returns:
        OpenAI-compatible response dict with 'choices', 'model', etc.
    """
    token = _get_token()

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            GITHUB_CHAT_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "GitHubCopilotSpacesUI/1.0",
            },
            json={
                "model": GITHUB_CHAT_MODEL,
                "messages": messages,
            },
        )
        if not response.is_success:
            logger.error(f"GitHub Models API error {response.status_code}: {response.text[:1000]}")
        response.raise_for_status()
        data = response.json()
        logger.info(
            f"GitHub Models response for space '{space_id}': "
            f"model={data.get('model', 'unknown')}"
        )
        return data


async def close_client() -> None:
    """No persistent global client — nothing to close."""
    pass

