from __future__ import annotations

import json
from pathlib import Path

from openmanus.log import logger

AVATARS_SEED_DIR = Path(__file__).resolve().parent.parent.parent / "seed" / "avatars"

_avatar_presets_cache: list[dict] | None = None

def list_avatar_presets() -> list[dict]:
    global _avatar_presets_cache
    if _avatar_presets_cache is not None:
        return _avatar_presets_cache
    manifest_path = AVATARS_SEED_DIR / "manifest.json"
    if not manifest_path.exists():
        logger.warning("avatar presets manifest 不存在: %s", manifest_path)
        _avatar_presets_cache = []
        return _avatar_presets_cache

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("avatar manifest 解析失败: %s", e)
        _avatar_presets_cache = []
        return _avatar_presets_cache
    presets = []
    for p in manifest.get("presets", []):
        pid = p.get("id", "")
        file = p.get("file", f"{pid}.svg")
        presets.append({
            "id": pid,
            "file": file,
            "seed": p.get("seed", ""),
            "url": f"/avatar-presets/{file}",
        })
    _avatar_presets_cache = presets
    return presets

def validate_preset_id(preset_id: str) -> str:
    if not preset_id:
        raise ValueError("preset_id is required")
    pid = preset_id.strip()
    if pid.endswith(".svg"):
        pid = pid[:-4]
    valid = {p["id"] for p in list_avatar_presets()}
    if pid not in valid:
        raise ValueError(
            f"unknown avatar preset: {preset_id!r} "
            f"(valid: {len(valid)} presets)"
        )
    return pid
