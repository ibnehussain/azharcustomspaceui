"""
Pydantic models for the Copilot Spaces MCP application.
"""

from pydantic import BaseModel
from typing import Optional


class QueryRequest(BaseModel):
    """Request body for querying a Copilot Space."""
    prompt: str
    conversationId: Optional[str] = None
    context: Optional[str] = None
