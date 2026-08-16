from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from pathlib import Path
from urllib.parse import urlparse

from openmanus.config import settings


def _is_postgres(url: str) -> bool:
    scheme = urlparse(url).scheme.lower()
    return scheme.startswith(("postgres", "postgresql"))

def _sqlite_path(url: str) -> str:
    path = url
    for prefix in ("sqlite:///", "sqlite://"):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    parent = Path(path).expanduser().parent
    parent.mkdir(parents=True, exist_ok=True)
    return path

async def get_checkpointer() -> BaseCheckpointSaver:
    url = settings.database_url

    if _is_postgres(url):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        conn = url.replace("postgresql+psycopg://", "postgresql://")
        saver = AsyncPostgresSaver.from_conn_string(conn)
        await saver.setup()
        return saver

    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    conn = await aiosqlite.connect(_sqlite_path(url))
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver
