"""Topics REST API — topic CRUD + history + reset + delete.

A topic is the top-level collaboration container (task/conversation group).
Each topic owns sessions, a whiteboard, a mailbox, and a workdir.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from ..agent_factory import build_agent, close_agent, compute_thread_id
from ..config import settings
from ..db import MAIN_TOPIC_ID, session_store, topic_store

router = APIRouter(prefix="/topics", tags=["topics"])


class CdBody(BaseModel):
    path: str = ""


@router.post("/{topic_id}/cd")
async def cd_topic(topic_id: str, body: CdBody) -> dict:
    """Switch a topic's workdir (shell-style cd).

    Behaves like a shell ``cd``:
      ``cd <subdir>``  — relative to current workdir
      ``cd ..``        — go up one level (stays at drive root if already there)
      ``cd D:\\path``  — absolute path
      ``cd``           — print current workdir (pwd)
    """
    from pathlib import Path

    topic = await topic_store.get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="topic not found")

    cur = Path(topic.get("workdir") or settings.workdir)
    path = body.path.strip()

    if not path:
        return {"ok": True, "workdir": str(cur), "action": "pwd"}

    raw = Path(path).expanduser()
    target = raw if raw.is_absolute() else cur / raw

    try:
        target = target.resolve()
    except (OSError, RuntimeError):
        target = target.absolute()

    if not target.exists() or not target.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"path does not exist or not a directory: {path}",
        )

    await topic_store.update_workdir(topic_id, str(target))
    settings.workdir = str(target)

    return {"ok": True, "workdir": str(target), "action": "cd"}


class TopicSummary(BaseModel):
    """A topic as shown in the topicList."""
    id: str
    title: str | None = None
    workdir: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    session_id: str | None = None
    kind: str = "root"
    status: str = "active"
    preview: str | None = None
    agents: list[str] = []


@router.get("", response_model=list[TopicSummary])
@router.get("/", response_model=list[TopicSummary], include_in_schema=False)
async def list_topics() -> list[dict]:
    """List all topics, newest first, with the latest session's info merged in."""
    topics = await topic_store.list()
    result = []
    for t in topics:
        sessions = await session_store.list_in_topic(t["id"])
        latest = sessions[0] if sessions else None
        preview = None
        if latest and latest.get("metadata"):
            preview = (latest["metadata"] or {}).get("preview")
        agent_names = list(dict.fromkeys(
            s["name"] for s in sessions if s.get("name")
        ))
        if not agent_names and t["id"] == "main":
            agent_names = ["Manus"]

        result.append({
            "id": t["id"],
            "title": t.get("title"),
            "workdir": t.get("workdir"),
            "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at"),
            "session_id": (latest or {}).get("id"),
            "kind": (latest or {}).get("kind", "root"),
            "status": (latest or {}).get("status", "active"),
            "preview": preview,
            "agents": agent_names,
        })
    return result


@router.get("/{topic_id}/history")
async def get_topic_history(topic_id: str) -> dict:
    """Get merged message history for all sessions in a topic."""
    sessions = await session_store.list_in_topic(topic_id)
    all_messages = []

    for s in sessions:
        name = s.get("name")
        if not name:
            continue
        thread_id = compute_thread_id(topic_id, name)
        try:
            agent, _ctx = await build_agent(s["id"])
            try:
                snapshot = await agent.aget_state(
                    {"configurable": {"thread_id": thread_id}}
                )
                msgs = (snapshot.values or {}).get("messages", [])
                for msg in msgs:
                    msg_type = getattr(msg, "type", "")
                    content = getattr(msg, "content", "")
                    msg_id = getattr(msg, "id", "") or ""

                    if msg_type == "human":
                        text = content if isinstance(content, str) else str(content)
                        all_messages.append({
                            "id": msg_id or f"u-{len(all_messages)}",
                            "role": "user",
                            "content": [{"type": "text", "text": text}],
                            "speaker": "user",
                            "session_id": s["id"],
                            "agent_name": name,
                        })
                    elif msg_type == "ai":
                        text = ""
                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, list):
                            text = " ".join(
                                b.get("text", "") for b in content
                                if isinstance(b, dict) and b.get("type") == "text"
                            )
                        all_messages.append({
                            "id": msg_id or f"a-{len(all_messages)}",
                            "role": "assistant",
                            "content": [{"type": "text", "text": text}] if text else [],
                            "thinking": "",
                            "speaker": f"agent:{name}",
                            "session_id": s["id"],
                            "agent_name": name,
                        })
            finally:
                await close_agent(agent)
        except Exception:
            pass

    return {"topic_id": topic_id, "messages": all_messages}


@router.post("/{topic_id}/reset")
async def reset_topic(topic_id: str) -> dict:
    """Reset a topic's conversation history (clear all checkpoints + sessions)."""
    sessions = await session_store.list_in_topic(topic_id)
    for s in sessions:
        name = s.get("name")
        if not name:
            continue
        thread_id = compute_thread_id(topic_id, name)
        try:
            agent, _ctx = await build_agent(s["id"])
            try:
                checkpointer = getattr(agent, "checkpointer", None)
                if checkpointer is not None and hasattr(checkpointer, "adelete_thread"):
                    await checkpointer.adelete_thread(thread_id)
            finally:
                await close_agent(agent)
        except Exception:  # noqa: BLE001
            pass
    await session_store.delete_in_topic(topic_id)
    return {"reset": topic_id}


@router.delete("/{topic_id}")
async def delete_topic(topic_id: str) -> dict:
    """Delete a topic and ALL its data (cascading cleanup)."""
    from ..whiteboard import whiteboard_store
    from ..mailbox import mailbox_store

    if topic_id == MAIN_TOPIC_ID:
        raise HTTPException(status_code=403, detail="main topic cannot be deleted")

    topic = await topic_store.get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="topic not found")

    # Delete checkpoints (must be before session rows)
    sessions = await session_store.list_in_topic(topic_id)
    for s in sessions:
        name = s.get("name")
        if not name:
            continue
        thread_id = compute_thread_id(topic_id, name)
        try:
            agent, _ctx = await build_agent(s["id"])
            try:
                checkpointer = getattr(agent, "checkpointer", None)
                if checkpointer is not None and hasattr(checkpointer, "adelete_thread"):
                    await checkpointer.adelete_thread(thread_id)
            finally:
                await close_agent(agent)
        except Exception:  # noqa: BLE001
            pass

    await session_store.delete_in_topic(topic_id)
    await whiteboard_store.delete_in_topic(topic_id)
    await mailbox_store.delete_in_topic(topic_id)
    await topic_store.delete(topic_id)

    return {"deleted": topic_id}
