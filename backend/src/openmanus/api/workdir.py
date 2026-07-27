"""Workdir REST API — validate workdir paths (used by /cd command)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["workdir"])


class ValidateWorkdir(BaseModel):
    path: str


@router.post("/workdir/validate")
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
