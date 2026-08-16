from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from openmanus.common.response import ApiListResponse, ApiResponse
from openmanus.config import settings
from openmanus.topics import flow
from openmanus.topics.entities import CdBody, TopicSummary
from openmanus.topics.store import session_store, topic_store

router = APIRouter(prefix="/topics", tags=["topics"])

@router.post("/{topic_id}/cd", response_model=ApiResponse)
async def api_cd_topic(topic_id: str, body: CdBody):
    try:
        topic = await topic_store.get(topic_id)
        if not topic:
            return ApiResponse.fail(message="topic not found")

        cur = Path(topic.workdir or settings.workdir)
        path = body.path.strip()

        if not path:
            return ApiResponse.ok({"ok": True, "workdir": str(cur), "action": "pwd"})

        raw = Path(path).expanduser()
        target = raw if raw.is_absolute() else cur / raw

        try:
            target = target.resolve()
        except (OSError, RuntimeError):
            target = target.absolute()

        if not target.exists() or not target.is_dir():
            return ApiResponse.fail(
                message=f"path does not exist or not a directory: {path}",
            )

        await topic_store.update_workdir(topic_id, str(target))
        settings.workdir = str(target)

        return ApiResponse.ok({"ok": True, "workdir": str(target), "action": "cd"})
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.get("", response_model=ApiListResponse)
@router.get("/", response_model=ApiListResponse, include_in_schema=False)
async def api_list_topics():
    try:
        topics = await topic_store.list_topics()
        result = []
        for t in topics:
            sessions = await session_store.list_in_topic(t.id)
            latest = sessions[0] if sessions else None
            preview = None
            if latest and latest.metadata:
                preview = latest.metadata.get("preview")
            agent_names = list(dict.fromkeys(
                s.name for s in sessions if s.name
            ))
            if not agent_names and t.id == "main":
                agent_names = ["Manus"]

            result.append(TopicSummary(
                id=t.id,
                title=t.title,
                workdir=t.workdir,
                created_at=t.created_at,
                updated_at=t.updated_at,
                session_id=latest.id if latest else None,
                kind=latest.kind if latest else "root",
                status=latest.status if latest else "active",
                preview=preview,
                agents=agent_names,
            ))
        return ApiListResponse.ok(data=result, total=len(result))
    except Exception as e:
        return ApiListResponse.fail(message=str(e))

@router.get("/{topic_id}/history", response_model=ApiResponse)
async def api_get_topic_history(topic_id: str):
    try:
        messages = await flow.get_topic_history(topic_id)
        return ApiResponse.ok({"topic_id": topic_id, "messages": messages})
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.post("/{topic_id}/reset", response_model=ApiResponse)
async def api_reset_topic(topic_id: str):
    try:
        await flow.reset_topic(topic_id)
        return ApiResponse.ok({"reset": topic_id})
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.delete("/{topic_id}", response_model=ApiResponse)
async def api_delete_topic(topic_id: str):
    try:
        await flow.delete_topic(topic_id)
        return ApiResponse.ok({"deleted": topic_id})
    except Exception as e:
        return ApiResponse.fail(message=str(e))
