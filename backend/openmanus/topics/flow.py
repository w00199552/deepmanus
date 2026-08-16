from __future__ import annotations

from typing import Any

from openmanus.common.exceptions import NotFoundError, TopicDeleteError
from openmanus.log import logger
from openmanus.runtime.convert import extract_reasoning
from openmanus.topics.entities import Session
from openmanus.topics.mailbox_store import mailbox_store
from openmanus.topics.store import MAIN_TOPIC_ID, session_store, topic_store
from openmanus.topics.whiteboard_store import whiteboard_store

def _default_agent_fallback(session: Session) -> str:
    if session.name:
        return session.name
    return "TeamLeader" if session.kind == "team" else "Manus"

async def _clear_thread(session: Session) -> None:
    from openmanus.agents.agent_factory import build_agent, close_agent, compute_thread_id

    thread_id = compute_thread_id(session.topic_id, _default_agent_fallback(session))
    try:
        agent, _ctx = await build_agent(session.id)
        try:
            checkpointer = getattr(agent, "checkpointer", None)
            if checkpointer is not None and hasattr(checkpointer, "adelete_thread"):
                await checkpointer.adelete_thread(thread_id)
        finally:
            await close_agent(agent)
    except Exception:
        logger.exception("failed to clear thread for session %s", session.id)

async def _clear_topic_checkpoints(topic_id: str) -> None:
    sessions = await session_store.list_in_topic(topic_id)
    for s in sessions:
        if not s.name:
            continue
        await _clear_thread(s)

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

async def get_topic_history(topic_id: str) -> list[dict[str, Any]]:
    from openmanus.agents.agent_factory import build_agent, close_agent, compute_thread_id

    sessions = await session_store.list_in_topic(topic_id)
    all_messages: list[dict[str, Any]] = []

    for s in sessions:
        name = s.name
        if not name:
            continue
        thread_id = compute_thread_id(topic_id, name)
        try:
            agent, _ctx = await build_agent(s.id)
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
                            "session_id": s.id,
                            "agent_name": name,
                        })
                    elif msg_type == "ai":
                        text = _content_to_text(content)
                        all_messages.append({
                            "id": msg_id or f"a-{len(all_messages)}",
                            "role": "assistant",
                            "content": [{"type": "text", "text": text}] if text else [],
                            "thinking": "",
                            "speaker": f"agent:{name}",
                            "session_id": s.id,
                            "agent_name": name,
                        })
            finally:
                await close_agent(agent)
        except Exception:
            logger.exception("failed reading history for session %s", s.id)

    return all_messages

async def get_session_timeline(session: Session) -> list[dict[str, Any]]:
    from openmanus.agents.agent_factory import build_agent, close_agent, compute_thread_id

    messages: list[dict[str, Any]] = []
    try:
        name = _default_agent_fallback(session)
        thread_id = compute_thread_id(session.topic_id, name)
        agent, _ctx = await build_agent(session.id)
        try:
            snapshot = await agent.aget_state(
                {"configurable": {"thread_id": thread_id}}
            )
        finally:
            await close_agent(agent)
        raw = (getattr(snapshot, "values", {}) or {}).get("messages", [])

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
                parts: list[dict[str, Any]] = []
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
                thinking = "".join(extract_reasoning(msg))
                if parts or thinking:
                    msg_obj: dict[str, Any] = {
                        "role": "assistant",
                        "id": mid or f"a-{len(messages)}",
                        "content": parts,
                        "metadata": {"speaker": session.name or "Manus"},
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
        logger.exception("failed reading timeline for session %s", session.id)

    return messages

async def reset_topic(topic_id: str) -> None:
    topic = await topic_store.get(topic_id)
    if not topic:
        raise NotFoundError(f"topic not found: {topic_id}")
    await _clear_topic_checkpoints(topic_id)
    await session_store.delete_in_topic(topic_id)

async def reset_session(session: Session) -> None:
    await _clear_thread(session)

async def delete_topic(topic_id: str) -> None:
    if topic_id == MAIN_TOPIC_ID:
        raise TopicDeleteError("main topic cannot be deleted")

    topic = await topic_store.get(topic_id)
    if not topic:
        raise NotFoundError(f"topic not found: {topic_id}")

    await _clear_topic_checkpoints(topic_id)
    await session_store.delete_in_topic(topic_id)
    await whiteboard_store.delete_in_topic(topic_id)
    await mailbox_store.delete_in_topic(topic_id)
    await topic_store.delete(topic_id)
