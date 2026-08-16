from __future__ import annotations

from fastapi import APIRouter

from openmanus.common.response import ApiListResponse, ApiResponse
from openmanus.topics import flow
from openmanus.topics.entities import (
    CreateSessionBody,
    UpdatePreviewBody,
    UpdateSessionBody,
)
from openmanus.topics.store import session_store
from openmanus.topics.whiteboard_store import whiteboard_store

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("", response_model=ApiResponse)
@router.post("/", response_model=ApiResponse, include_in_schema=False)
async def api_create_session(body: CreateSessionBody):
    try:
        s = await session_store.create(
            kind=body.kind,
            name=body.name,
            title=body.title,
            workdir=body.workdir,
            topic_id=body.topic_id,
            metadata=body.metadata,
        )
        return ApiResponse.ok(s)
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.get("", response_model=ApiListResponse)
@router.get("/", response_model=ApiListResponse, include_in_schema=False)
async def api_list_sessions(
    kind: str | None = None,
    topic_id: str | None = None,
):
    try:
        sessions = await session_store.list(kind=kind, topic_id=topic_id)
        return ApiListResponse.ok(data=sessions, total=len(sessions))
    except Exception as e:
        return ApiListResponse.fail(message=str(e))

@router.get("/{session_id}", response_model=ApiResponse)
async def api_get_session(session_id: str):
    try:
        s = await session_store.get(session_id)
        if not s:
            return ApiResponse.fail(message="session not found")
        messages = await flow.get_session_timeline(s)
        data = s.model_dump()
        data["messages"] = messages
        return ApiResponse.ok(data)
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.patch("/{session_id}", response_model=ApiResponse)
async def api_update_session(session_id: str, body: UpdateSessionBody):
    try:
        s = await session_store.update(
            session_id,
            title=body.title,
            status=body.status,
            workdir=body.workdir,
            metadata=body.metadata,
        )
        if not s:
            return ApiResponse.fail(message="session not found")
        return ApiResponse.ok(s)
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.post("/{session_id}/preview", response_model=ApiResponse)
async def api_set_preview(session_id: str, body: UpdatePreviewBody):
    try:
        existing = await session_store.get(session_id)
        if not existing:
            return ApiResponse.fail(message="session not found")
        md = dict(existing.metadata or {})
        md["preview"] = (body.preview or "")[:120]
        if body.speaker:
            md["preview_speaker"] = body.speaker
        s = await session_store.update(session_id, metadata=md)
        return ApiResponse.ok(s or existing)
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.delete("/{session_id}", response_model=ApiResponse)
async def api_delete_session(session_id: str):
    try:
        ok = await session_store.delete(session_id)
        if not ok:
            return ApiResponse.fail(message="session not found")
        return ApiResponse.ok({"deleted": session_id})
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.post("/{session_id}/reset", response_model=ApiResponse)
async def api_reset_session(session_id: str):
    try:
        s = await session_store.get(session_id)
        if not s:
            return ApiResponse.fail(message="session not found")
        await flow.reset_session(s)
        return ApiResponse.ok({"reset": session_id})
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.get("/{session_id}/whiteboard", response_model=ApiResponse)
async def api_get_whiteboard(session_id: str):
    try:
        s = await session_store.get(session_id)
        if not s:
            return ApiResponse.fail(message="session not found")
        topic_id = s.topic_id or "main"
        notes = await whiteboard_store.list_in_topic(topic_id)
        return ApiResponse.ok({
            "session_id": session_id,
            "topic_id": topic_id,
            "notes": [n.model_dump() for n in notes],
        })
    except Exception as e:
        return ApiResponse.fail(message=str(e))
