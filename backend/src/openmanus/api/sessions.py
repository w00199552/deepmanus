"""Sessions REST API.

CRUD for sessions (the agent-conversation nodes). The history-flattening in
``get_session`` reads the checkpointer and returns an assistant-ui-compatible
message shape so the frontend can drop it straight into a Thread. Live streaming
lives in ``streams.py`` (POST /sessions/:id/messages, GET /sessions/:id/stream).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Any

from ..agent_factory import build_agent, close_agent, compute_thread_id
from ..db import session_store, topic_store

router = APIRouter(prefix="/sessions", tags=["sessions"])
topics_router = APIRouter(prefix="/topics", tags=["topics"])


class CreateSession(BaseModel):
    kind: str = "root"
    name: str | None = None
    title: str | None = None
    workdir: str | None = None
    topic_id: str = "main"
    metadata: dict[str, Any] = {}


class UpdateSession(BaseModel):
    title: str | None = None
    status: str | None = None
    workdir: str | None = None
    metadata: dict[str, Any] | None = None


class SessionSummary(BaseModel):
    id: str
    kind: str
    name: str | None = None
    status: str
    title: str | None = None
    model: str | None = None
    workdir: str | None = None
    topic_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@router.post("", response_model=dict, status_code=201)
@router.post("/", response_model=dict, status_code=201, include_in_schema=False)
async def create_session(body: CreateSession) -> dict:
    return await session_store.create(
        kind=body.kind,
        name=body.name,
        title=body.title,
        workdir=body.workdir,
        topic_id=body.topic_id,
        metadata=body.metadata,
    )


@router.get("", response_model=list[SessionSummary])
@router.get("/", response_model=list[SessionSummary], include_in_schema=False)
async def list_sessions(
    kind: str | None = None,
    topic_id: str | None = None,
) -> list[dict]:
    """List sessions.

    Filters (combinable):
      - ``kind``        only sessions of this kind
      - ``topic_id``    only members of this topic
    With no filter, returns everything.
    """
    if topic_id is not None:
        return await session_store.list(kind=kind, topic_id=topic_id)
    return await session_store.list(kind=kind)


@router.get("/{session_id}")
async def get_session(session_id: str, request: Request) -> dict:
    """Session metadata + message history as an assistant-ui-compatible timeline.

    The history is read from the deepagents checkpointer for this thread and
    flattened into ThreadMessage-shaped entries the frontend MessagesStore can
    use directly:

      { role:'user'|'assistant', id, content:[ {type:'text',text} | {type:'tool-call',...} ] }

    An AIMessage may carry text AND tool_calls; each becomes a content part on
    the same assistant message, preserving the real text→tool ordering. A later
    ToolMessage back-fills the matching tool-call part's result.
    """
    s = await session_store.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")

    messages: list[dict] = []
    try:
        agent = await build_agent(session_id)
        try:
            name = s.get("name") or ("TeamLeader" if s.get("kind") == "team" else "Manus")
            topic_id = s.get("topic_id") or "main"
            thread_id = compute_thread_id(topic_id, name)
            snapshot = await agent.aget_state(
                {"configurable": {"thread_id": thread_id}}
            )
        finally:
            await close_agent(agent)
        raw = (getattr(snapshot, "values", {}) or {}).get("messages", [])

        # tool_call_id -> (msg_index, part_index) so a ToolMessage can back-fill.
        tool_part_index: dict[str, tuple[int, int]] = {}

        for msg in raw:
            mtype = getattr(msg, "type", "")
            mid = getattr(msg, "id", None) or ""
            content = getattr(msg, "content", "")

            if mtype == "human":
                text = _content_to_text(content)
                if text.strip():
                    messages.append({
                        "role": "user", "id": mid or f"u-{len(messages)}",
                        "content": [{"type": "text", "text": text}],
                        "metadata": {"speaker": "user"},
                    })

            elif mtype == "ai":
                parts: list[dict] = []
                text = _content_to_text(content)
                if text.strip():
                    parts.append({"type": "text", "text": text})
                for tc in getattr(msg, "tool_calls", None) or []:
                    tcid = tc.get("id") or ""
                    parts.append({
                        "type": "tool-call",
                        "toolCallId": tcid,
                        "toolName": tc.get("name", "tool"),
                        "args": _stringify_args(tc.get("args")),
                        "result": None,
                    })
                    tool_part_index[tcid] = (len(messages), len(parts) - 1)
                # reasoning/thinking trace (GLM reasoning_content) — surfaced so
                # history reload shows the thinking region too.
                from ..engine import _extract_reasoning
                thinking = "".join(_extract_reasoning(msg))
                # include the message even if only thinking (no text/tool) so the
                # user can review prior reasoning on history reload.
                if parts or thinking:
                    msg_obj: dict = {
                        "role": "assistant",
                        "id": mid or f"a-{len(messages)}",
                        "content": parts,
                        "metadata": {"speaker": (s.get("name") or "Manus")},
                    }
                    if thinking:
                        msg_obj["thinking"] = thinking
                    messages.append(msg_obj)

            elif mtype == "tool":
                tcid = getattr(msg, "tool_call_id", "") or ""
                loc = tool_part_index.get(tcid)
                if loc is not None:
                    mi, pi = loc
                    messages[mi]["content"][pi]["result"] = _content_to_text(content)
    except Exception:
        # history is best-effort; never fail the whole response
        pass

    s["messages"] = messages
    return s


def _content_to_text(content: Any) -> str:
    if isinstance(content, list):
        return " ".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        ).strip()
    return str(content) if content else ""


def _stringify_args(args: Any) -> str:
    if not args:
        return ""
    try:
        import json

        return json.dumps(args, ensure_ascii=False)
    except Exception:
        return str(args)


class UpdatePreview(BaseModel):
    preview: str
    speaker: str | None = None


@router.patch("/{session_id}")
async def update_session(session_id: str, body: UpdateSession) -> dict:
    s = await session_store.update(
        session_id,
        title=body.title,
        status=body.status,
        workdir=body.workdir,
        metadata=body.metadata,
    )
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return s


@router.post("/{session_id}/preview")
async def set_preview(session_id: str, body: UpdatePreview) -> dict:
    """Set the session's last-message preview (and optionally speaker).

    Merged into metadata (NOT a full overwrite) so existing metadata like
    parent/role/members is preserved.
    """
    existing = await session_store.get(session_id)
    if not existing:
        raise HTTPException(status_code=404, detail="session not found")
    md = dict(existing.get("metadata") or {})
    md["preview"] = (body.preview or "")[:120]
    if body.speaker:
        md["preview_speaker"] = body.speaker
    s = await session_store.update(session_id, metadata=md)
    return s or existing


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    ok = await session_store.delete(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return {"deleted": session_id}


@router.post("/{session_id}/reset")
async def reset_session(session_id: str, request: Request) -> dict:
    """Reset a session's conversation history (clear the checkpointer thread).

    Used by the default entry's "new chat": the default item is permanent and
    can't be deleted, so starting fresh means wiping its message history. The
    session row itself is untouched.
    """
    if not await session_store.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    try:
        s = await session_store.get(session_id)
        name = (s or {}).get("name") or ("TeamLeader" if (s or {}).get("kind") == "team" else "Manus")
        topic_id = (s or {}).get("topic_id") or "main"
        thread_id = compute_thread_id(topic_id, name)
        agent = await build_agent(session_id)
        try:
            checkpointer = getattr(agent, "checkpointer", None)
            if checkpointer is not None and hasattr(checkpointer, "adelete_thread"):
                await checkpointer.adelete_thread(thread_id)
        finally:
            await close_agent(agent)
    except Exception:
        pass
    return {"reset": session_id}


# --- Mailbox + whiteboard views (per session / per topic) --------------------

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


@router.get("/{session_id}/whiteboard")
async def get_whiteboard(session_id: str) -> dict:
    """Whiteboard notes in this session's topic."""
    s = await session_store.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    from ..whiteboard import whiteboard_store

    topic_id = s.get("topic_id") or "main"
    notes = await whiteboard_store.list_in_topic(topic_id)
    return {"session_id": session_id, "topic_id": topic_id, "notes": notes}


# --- Workdir validation (top-level, not under /sessions) --------------------
workdir_router = APIRouter(tags=["workdir"])


class ValidateWorkdir(BaseModel):
    path: str


@workdir_router.post("/workdir/validate")
async def validate_workdir(body: ValidateWorkdir) -> dict:
    """Check that a workdir path exists and is a directory."""
    from pathlib import Path

    p = Path(body.path).expanduser()
    exists = p.exists()
    is_dir = p.is_dir()
    entries: list[str] = []
    if is_dir:
        try:
            entries = sorted([e.name for e in p.iterdir()])[:12]
        except (PermissionError, OSError):
            entries = []
    return {
        "path": str(p),
        "exists": exists,
        "is_dir": is_dir,
        "valid": exists and is_dir,
        "entries": entries,
    }


# ─── Topics API ────────────────────────────────────────────────────────────


class TopicSummary(BaseModel):
    """A topic as shown in the topicList (session list replacement)."""
    id: str
    title: str | None = None
    workdir: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # Aggregated from the topic's sessions for display:
    session_id: str | None = None     # latest session id (for SSE subscription)
    agent_name: str | None = None     # the (latest) agent in this topic
    kind: str = "root"                # the (latest) session kind
    status: str = "active"            # the (latest) session status
    preview: str | None = None        # last message preview (from metadata)
    agents: list[str] = []            # all agent names in this topic (deduped, for avatars)


@topics_router.get("", response_model=list[TopicSummary])
@topics_router.get("/", response_model=list[TopicSummary], include_in_schema=False)
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
        # Extract unique agent names for avatar rendering
        agent_names = list(dict.fromkeys(
            s["name"] for s in sessions if s.get("name")
        ))
        # main topic with no sessions yet → default to Manus
        if not agent_names and t["id"] == "main":
            agent_names = ["Manus"]

        result.append({
            "id": t["id"],
            "title": t.get("title"),
            "workdir": t.get("workdir"),
            "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at"),
            "session_id": (latest or {}).get("id"),
            "agent_name": (latest or {}).get("name"),
            "kind": (latest or {}).get("kind", "root"),
            "status": (latest or {}).get("status", "active"),
            "preview": preview,
            "agents": agent_names,
        })
    return result


@topics_router.get("/{topic_id}/history")
async def get_topic_history(topic_id: str) -> dict:
    """Get merged message history for all sessions in a topic.

    Loads each session's checkpointer history (via thread_id) and merges them
    into a single timeline sorted by message order. This is what the frontend
    renders when switching to a topic (replaces per-session history loading).
    """
    from ..agent_factory import build_agent, close_agent, compute_thread_id

    sessions = await session_store.list_in_topic(topic_id)
    all_messages = []

    for s in sessions:
        name = s.get("name")
        if not name:
            continue
        thread_id = compute_thread_id(topic_id, name)
        try:
            agent, ctx = await build_agent(s["id"])
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
            pass  # session has no history yet — skip

    return {"topic_id": topic_id, "messages": all_messages}


@topics_router.post("/{topic_id}/reset")
async def reset_topic(topic_id: str) -> dict:
    """Reset a topic's conversation history (clear all checkpoints + sessions).

    Used by "new chat": clears all agent threads in this topic and deletes
    all session rows, so the next message creates a fresh session with no
    memory. The topic itself stays.
    """
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
    # Delete all session rows (next message will create fresh ones)
    await session_store.delete_in_topic(topic_id)
    return {"reset": topic_id}


@topics_router.delete("/{topic_id}")
async def delete_topic(topic_id: str) -> dict:
    """Delete a topic and ALL its data (cascading cleanup).

    Deletion order (checkpoints must go before sessions rows, because
    adelete_thread needs build_agent which reads the session row):

    1. Reject 'main' (entry topic, cannot be deleted)
    2. Load all sessions in the topic
    3. For each session: build_agent → adelete_thread → close_agent
       (deletes LangGraph checkpoints by thread_id)
    4. Delete sessions rows (DELETE FROM sessions WHERE topic_id = ?)
    5. Delete whiteboard notes (whiteboard_store.delete_in_topic)
    6. Delete mailbox messages (mailbox_store.delete_in_topic)
    7. Delete topic row (topic_store.delete)
    """
    from ..db import MAIN_TOPIC_ID
    from ..whiteboard import whiteboard_store
    from ..mailbox import mailbox_store

    if topic_id == MAIN_TOPIC_ID:
        raise HTTPException(status_code=403, detail="main topic cannot be deleted")

    topic = await topic_store.get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="topic not found")

    # Step 2-3: delete checkpoints (must be before session rows)
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
            pass  # checkpoint may not exist or agent build may fail — skip

    # Step 4-7: delete rows (order doesn't matter among these)
    await session_store.delete_in_topic(topic_id)
    await whiteboard_store.delete_in_topic(topic_id)
    await mailbox_store.delete_in_topic(topic_id)
    await topic_store.delete(topic_id)

    return {"deleted": topic_id}
