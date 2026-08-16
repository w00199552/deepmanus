from __future__ import annotations

from pathlib import Path

from openmanus.config import settings


def get_db_path() -> str:
    url = settings.database_url
    path = url
    for prefix in ("sqlite:///", "sqlite://"):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    p = Path(path)
    return str(p.with_name("openmanus.db"))
