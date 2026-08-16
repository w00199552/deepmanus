from __future__ import annotations

import os
import sys
from pathlib import Path

from openmanus.log import logger

_DEFAULT_EMBED_DIR = Path(__file__).resolve().parent / "python"

EMBED_PYTHON_DIR: Path = (
    Path(os.environ.get("OPENMANUS_PYTHON_HOME", _DEFAULT_EMBED_DIR))
    if os.environ.get("OPENMANUS_PYTHON_HOME")
    else _DEFAULT_EMBED_DIR
)

if sys.platform == "win32":
    _INTERPRETER_NAMES = ("python.exe", "python3.exe")
else:
    _INTERPRETER_NAMES = ("python3", "python")

def find_embed_python() -> Path | None:
    for name in _INTERPRETER_NAMES:
        candidate = EMBED_PYTHON_DIR / name
        if candidate.is_file():
            return candidate
    return None

def build_skill_env() -> dict[str, str] | None:
    interp = find_embed_python()
    if interp is None:
        return None
    embed_dir = str(interp.parent)
    inherited_path = os.environ.get("PATH", "")
    if inherited_path and inherited_path.split(os.pathsep)[0] == embed_dir:
        return None
    new_path = (
        embed_dir if not inherited_path else os.pathsep.join([embed_dir, inherited_path])
    )
    return {"PATH": new_path}
