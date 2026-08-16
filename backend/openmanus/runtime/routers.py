from __future__ import annotations

import uuid
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from openmanus.common.response import ApiResponse
from openmanus.runtime import event_schema as E
from openmanus.runtime.channels import channels, drain_sessions, fan_in
from openmanus.runtime.engine import engine
from openmanus.skills.loader import skill_loader
from openmanus.topics.store import session_store, topic_store

router = APIRouter(tags=["streams"])

class PostMessageBody(BaseModel):

    content: str = Field(description="消息正文")
    target_agent: str | None = Field(
        default=None,
        description="@ 提及的目标 agent；None = topic 的默认 agent",
    )

async def _emit_system_text(session_id: str, text: str) -> None:
    queue = channels.get_queue(session_id)
    msg_id = f"skill-{uuid.uuid4().hex}"
    await queue.put(E.frame(E.ev_message_start(session_id=session_id, message_id=msg_id, speaker="system")))
    await queue.put(E.frame(E.ev_text_delta(session_id=session_id, message_id=msg_id, speaker="system", delta=text)))
    await queue.put(E.frame(E.ev_message_end(session_id=session_id, message_id=msg_id, speaker="system")))
    await queue.put(E.frame(E.ev_done(session_id=session_id)))
    await queue.put(E.done_sentinel(session_id))

def _apply_skill_command(content: str) -> tuple[str, str | None]:
    lower = content.lower()
    if not (lower.startswith("skill ") or lower == "skill"
            or lower.startswith("/skill ") or lower == "/skill"):
        return content, None
    stripped = content.lstrip("/")
    return stripped[5:].strip(), "skill"

@router.post("/sessions/{session_id}/messages", response_model=ApiResponse)
async def api_post_message(session_id: str, body: PostMessageBody):
    try:
        s = await session_store.get(session_id)
        if not s:
            return ApiResponse.fail(message="session not found")

        content = body.content.strip()

        skill_name, action = _apply_skill_command(content)
        if action == "skill":
            if not skill_name:
                names = skill_loader.all_names()
                text = "📋 Available skills:\n" + (
                    "\n".join(f"  skill {n}" for n in names) if names else "(no skills installed)"
                )
                await _emit_system_text(session_id, text)
                return ApiResponse.ok({"ok": True, "session_id": session_id, "action": "skill-list"})

            sdir = skill_loader.skill_dir(skill_name)
            if not sdir or not sdir.exists():
                text = f"❌ Skill '{skill_name}' not found. Use /skill to list available."
                await _emit_system_text(session_id, text)
                return ApiResponse.ok({"ok": True, "session_id": session_id, "action": "skill-notfound"})

            skill_md = (sdir / "SKILL.md").read_text(encoding="utf-8")
            content = (
                "The user activated the skill '{skill_name}'. Follow its instructions "
                "for this and subsequent messages until told otherwise.\n\n"
                "--- Skill: {skill_name} ---\n{skill_md}\n--- End Skill ---\n\n"
            ).format(skill_name=skill_name, skill_md=skill_md)

        speaker = s.name or ("TeamLeader" if s.kind == "team" else "Manus")

        await engine.run(
            session_id=session_id, prompt=content, speaker=speaker,
            mode="async",
        )
        return ApiResponse.ok({"ok": True, "session_id": session_id})
    except Exception as e:
        return ApiResponse.fail(message=str(e))

def _default_agent_name(topic_id: str, sessions: list) -> str:
    if topic_id == "main":
        return "Manus"
    names = [s.name for s in sessions if s.name]
    if "TeamLeader" in names:
        return "TeamLeader"
    if names:
        return names[0]
    return "Manus"

def _find_default_session(topic_id: str, sessions: list):
    if topic_id == "main":
        for s in sessions:
            if s.name == "Manus":
                return s
        return None
    for s in sessions:
        if s.name == "TeamLeader":
            return s
    for s in sessions:
        if s.kind in ("subagent", "team"):
            return s
    return sessions[0] if sessions else None

@router.post("/topics/{topic_id}/messages", response_model=ApiResponse)
async def api_post_topic_message(topic_id: str, body: PostMessageBody):
    try:
        topic = await topic_store.get(topic_id)
        if not topic:
            return ApiResponse.fail(message="topic not found")

        sessions = await session_store.list_in_topic(topic_id)

        if body.target_agent:
            target_session = None
            for s in sessions:
                if s.name == body.target_agent:
                    target_session = s
                    break
            if not target_session:
                target_session = await session_store.create(
                    topic_id=topic_id, kind="subagent",
                    name=body.target_agent, title=body.target_agent,
                )
        else:
            target_session = _find_default_session(topic_id, sessions)
            if not target_session:
                agent_name = _default_agent_name(topic_id, sessions)
                target_session = await session_store.create(
                    topic_id=topic_id,
                    kind="root" if topic_id == "main" else "subagent",
                    name=agent_name, title=agent_name,
                )

        speaker = target_session.name or "Manus"
        await engine.run(
            session_id=target_session.id,
            prompt=body.content,
            speaker=speaker,
            mode="async",
        )
        return ApiResponse.ok({"ok": True, "session_id": target_session.id})
    except Exception as e:
        return ApiResponse.fail(message=str(e))

async def _sse_byte_stream(
    topic: str | None, sessions: list[str] | None
):
    if topic:
        async for raw in fan_in(topic_id=topic):
            yield raw
        return
    if sessions:
        async for raw in drain_sessions(sessions):
            yield raw
        return
    yield "data: [DONE]\n\n"

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

@router.get("/stream")
async def api_stream(
    topic: str | None = Query(default=None),
    sessions: str | None = Query(default=None),
) -> StreamingResponse:
    sess_list = [s.strip() for s in sessions.split(",")] if sessions else None
    return StreamingResponse(
        _sse_byte_stream(topic, sess_list),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )

@router.get("/health", response_model=ApiResponse)
async def api_health():
    from openmanus.config import settings

    return ApiResponse.ok({
        "status": "ok",
        "model": settings.model,
        "workdir": settings.workdir,
    })
