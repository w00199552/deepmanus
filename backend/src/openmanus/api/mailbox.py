"""Mailbox REST API — read an agent's inbox (inter-agent messages)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import session_store

router = APIRouter(prefix="/sessions", tags=["mailbox"])


@router.get("/{session_id}/mailbox")
async def get_mailbox(session_id: str, unread_only: bool = False) -> dict:
    """An agent's inbox in this session's topic."""
    s = await session_store.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    from ..mailbox import mailbox_store

    topic_id = s.get("topic_id") or "main"
    agent_name = s.get("name") or "Manus"
    msgs = await mailbox_store.inbox(topic_id, agent_name, unread_only=unread_only)
    return {"session_id": session_id, "messages": msgs}
