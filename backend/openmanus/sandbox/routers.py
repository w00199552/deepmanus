from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from openmanus.common.response import ApiResponse
from openmanus.config import settings
from openmanus.sandbox import service
from openmanus.sandbox.entities import FileNode, PathBody, WriteFileBody

router = APIRouter(prefix="/sandbox", tags=["sandbox"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

@router.get("/tree", response_model=ApiResponse)
async def api_get_tree(workdir: str | None = Query(None)):
    try:
        return ApiResponse.ok(service.get_tree(workdir))
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.get("/children", response_model=ApiResponse)
async def api_get_children(
    path: str = Query(""),
    workdir: str | None = Query(None),
):
    try:
        return ApiResponse.ok(service.list_children(path, workdir))
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.get("/read", response_model=ApiResponse)
async def api_read_file(
    path: str = Query(...),
    workdir: str | None = Query(None),
):
    try:
        return ApiResponse.ok(service.read_file(path, workdir))
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.put("/write", response_model=ApiResponse)
async def api_write_file(body: WriteFileBody):
    try:
        return ApiResponse.ok(service.write_file(body.path, body.content, body.workdir))
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.delete("/delete", response_model=ApiResponse)
async def api_delete_path(body: PathBody):
    try:
        return ApiResponse.ok(service.delete_path(body.path, body.workdir))
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.post("/mkdir", response_model=ApiResponse)
async def api_make_dir(body: PathBody):
    try:
        return ApiResponse.ok(service.make_dir(body.path, body.workdir))
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.post("/create", response_model=ApiResponse)
async def api_create_file(body: PathBody):
    try:
        return ApiResponse.ok(service.create_file(body.path, body.workdir))
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.get("/watch")
async def api_watch_files(
    request: Request,
    workdir: str | None = Query(None),
) -> StreamingResponse:
    wd_str = workdir or settings.workdir
    loop = asyncio.get_running_loop()
    q = service.watcher.start(wd_str, loop)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            service.watcher.stop(q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
