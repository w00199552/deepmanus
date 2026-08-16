from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query

from openmanus.common.response import ApiListResponse, ApiResponse
from openmanus.sandbox.entities import FileNode
from openmanus.tools.entities import Tool
from openmanus.tools.tool_loader import TOOLS_DIR, tool_loader

router = APIRouter(prefix="/tools-api", tags=["tools"])

_BUILTIN_TOOLS = [
    Tool(name="dispatch", description="Delegate a task to another agent", source="builtin"),
    Tool(name="send_message", description="Send a message to another agent", source="builtin"),
    Tool(name="read_mailbox", description="Read your inbox messages", source="builtin"),
    Tool(name="whiteboard_write", description="Write an artefact to the whiteboard", source="builtin"),
    Tool(name="whiteboard_read", description="Read whiteboard artefacts", source="builtin"),
]

def _classify_file(ext: str) -> str:
    if ext == ".md":
        return "markdown"
    if ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".sh", ".json", ".yaml", ".yml", ".css"):
        return "code"
    return "text"

@router.get("", response_model=ApiListResponse)
@router.get("/", response_model=ApiListResponse, include_in_schema=False)
async def api_list_tools():
    try:
        tools = list(_BUILTIN_TOOLS)
        for name, instance in tool_loader.tools.items():
            tools.append(Tool(
                name=name,
                description=getattr(instance, "description", "")[:200],
                source="user",
            ))
        return ApiListResponse.ok(data=tools, total=len(tools))
    except Exception as e:
        return ApiListResponse.fail(message=str(e))

@router.get("/{name}/tree", response_model=ApiResponse)
async def api_get_tool_tree(name: str):
    try:
        tool_dir = TOOLS_DIR / name
        if not tool_dir.exists():
            return ApiResponse.fail(message="tool not found (built-in tools have no files)")

        def build_tree(path: Path, relative: str) -> FileNode:
            node = FileNode(
                name=path.name,
                path=relative,
                type="dir" if path.is_dir() else "file",
            )
            if path.is_dir():
                for child in sorted(path.iterdir(), key=lambda c: (not c.is_dir(), c.name)):
                    child_rel = f"{relative}/{child.name}" if relative else child.name
                    node.children.append(build_tree(child, child_rel))
            return node

        return ApiResponse.ok(build_tree(tool_dir, ""))
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.get("/{name}/file", response_model=ApiResponse)
async def api_get_tool_file(name: str, path: str = Query(...)):
    try:
        tool_dir = TOOLS_DIR / name
        if not tool_dir.exists():
            return ApiResponse.fail(message="tool not found")

        target = (tool_dir / path).resolve()
        try:
            target.relative_to(tool_dir.resolve())
        except ValueError:
            return ApiResponse.fail(message="path outside tool directory")

        if not target.exists() or not target.is_file():
            return ApiResponse.fail(message="file not found")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = "(binary file)"

        return ApiResponse.ok({
            "path": path,
            "name": target.name,
            "content": content,
            "file_type": _classify_file(target.suffix.lower()),
        })
    except Exception as e:
        return ApiResponse.fail(message=str(e))
