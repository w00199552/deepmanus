from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query

from openmanus.common.response import ApiListResponse, ApiResponse
from openmanus.sandbox.entities import FileNode
from openmanus.skills.loader import skill_loader

router = APIRouter(prefix="/skills", tags=["skills"])

def _classify_file(ext: str) -> str:
    if ext == ".md":
        return "markdown"
    if ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".sh", ".json", ".yaml", ".yml", ".css", ".html", ".xml", ".sql"):
        return "code"
    return "text"

@router.get("", response_model=ApiListResponse)
@router.get("/", response_model=ApiListResponse, include_in_schema=False)
async def api_list_skills():
    try:
        skills = list(skill_loader.skills.values())
        return ApiListResponse.ok(data=skills, total=len(skills))
    except Exception as e:
        return ApiListResponse.fail(message=str(e))

@router.get("/{name}/tree", response_model=ApiResponse)
async def api_get_skill_tree(name: str):
    try:
        sdir = skill_loader.skill_dir(name)
        if not sdir or not sdir.exists():
            return ApiResponse.fail(message="skill not found")

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

        return ApiResponse.ok(build_tree(sdir, ""))
    except Exception as e:
        return ApiResponse.fail(message=str(e))

@router.get("/{name}/file", response_model=ApiResponse)
async def api_get_skill_file(name: str, path: str = Query(...)):
    try:
        sdir = skill_loader.skill_dir(name)
        if not sdir or not sdir.exists():
            return ApiResponse.fail(message="skill not found")

        target = (sdir / path).resolve()
        try:
            target.relative_to(sdir.resolve())
        except ValueError:
            return ApiResponse.fail(message="path outside skill directory")

        if not target.exists() or not target.is_file():
            return ApiResponse.fail(message="file not found")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = "(binary file, cannot display)"

        return ApiResponse.ok({
            "path": path,
            "name": target.name,
            "content": content,
            "file_type": _classify_file(target.suffix.lower()),
        })
    except Exception as e:
        return ApiResponse.fail(message=str(e))
