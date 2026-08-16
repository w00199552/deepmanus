from __future__ import annotations

import json
import uuid
from typing import Any

import aiosqlite

from openmanus.common.exceptions import NotFoundError, TopicDeleteError
from openmanus.config import settings
from openmanus.db import get_db_path
from openmanus.log import logger
from openmanus.topics.entities import Session, Topic

MAIN_TOPIC_ID = "main"

def _row_to_topic(row: aiosqlite.Row) -> Topic:
    return Topic(
        id=row["id"],
        title=row["title"],
        workdir=row["workdir"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

def _row_to_session(row: aiosqlite.Row) -> Session:
    try:
        metadata = json.loads(row["metadata"] or "{}")
    except (TypeError, ValueError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return Session(
        id=row["id"],
        topic_id=row["topic_id"],
        kind=row["kind"],
        name=row["name"],
        status=row["status"],
        title=row["title"],
        model=row["model"],
        workdir=row["workdir"],
        metadata=metadata,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

class TopicStore:

    @classmethod
    async def create(
        cls,
        *,
        topic_id: str | None = None,
        title: str | None = None,
        workdir: str | None = None,
    ) -> Topic:
        tid = topic_id or f"topic-{uuid.uuid4().hex}"
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                """INSERT INTO topics (id, title, workdir)
                   VALUES (?, ?, ?)""",
                (tid, title, workdir or settings.workdir),
            )
            await db.commit()
        created = await cls.get(tid)
        assert created is not None
        return created

    @classmethod
    async def get(cls, topic_id: str) -> Topic | None:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM topics WHERE id = ?", (topic_id,)
            )
            row = await cur.fetchone()
            return _row_to_topic(row) if row else None

    @classmethod
    async def ensure_main(cls) -> Topic:
        existing = await cls.get(MAIN_TOPIC_ID)
        if existing:
            return existing
        return await cls.create(
            topic_id=MAIN_TOPIC_ID, title="Main", workdir=settings.workdir,
        )

    @classmethod
    async def update_workdir(cls, topic_id: str, workdir: str) -> Topic:
        await cls._update_column(topic_id, "workdir", workdir)
        updated = await cls.get(topic_id)
        if updated is None:
            raise NotFoundError(f"topic not found: {topic_id}")
        return updated

    @classmethod
    async def update_title(cls, topic_id: str, title: str) -> Topic:
        await cls._update_column(topic_id, "title", title)
        updated = await cls.get(topic_id)
        if updated is None:
            raise NotFoundError(f"topic not found: {topic_id}")
        return updated

    @classmethod
    async def _update_column(cls, topic_id: str, column: str, value: str) -> None:
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                f"UPDATE topics SET {column} = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (value, topic_id),
            )
            await db.commit()

    @classmethod
    async def list_topics(cls) -> list[Topic]:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM topics ORDER BY updated_at DESC"
            )
            rows = await cur.fetchall()
            return [_row_to_topic(r) for r in rows]

    @classmethod
    async def delete(cls, topic_id: str) -> bool:
        if topic_id == MAIN_TOPIC_ID:
            raise TopicDeleteError("main topic cannot be deleted")
        async with aiosqlite.connect(get_db_path()) as db:
            cur = await db.execute(
                "DELETE FROM topics WHERE id = ?", (topic_id,)
            )
            await db.commit()
            return cur.rowcount > 0

class SessionStore:

    @classmethod
    async def create(
        cls,
        *,
        topic_id: str,
        kind: str = "root",
        name: str | None = None,
        title: str | None = None,
        model: str | None = None,
        workdir: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Session:
        sid = session_id or f"sess-{uuid.uuid4().hex}"
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                """INSERT INTO sessions
                   (id, topic_id, kind, name, title, model, workdir, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sid,
                    topic_id,
                    kind,
                    name,
                    title,
                    model or settings.model,
                    workdir or settings.workdir,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            await db.commit()
        created = await cls.get(sid)
        assert created is not None
        return created

    @classmethod
    async def get(cls, session_id: str) -> Session | None:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            row = await cur.fetchone()
            return _row_to_session(row) if row else None

    @classmethod
    async def ensure_exists(
        cls, session_id: str, *, topic_id: str, title: str | None = None
    ) -> Session:
        existing = await cls.get(session_id)
        if existing:
            return existing
        return await cls.create(
            session_id=session_id, topic_id=topic_id, kind="root", title=title
        )

    @classmethod
    async def list(
        cls,
        kind: str | None = None,
        topic_id: str | None = None,
    ) -> list[Session]:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            clauses: list[str] = []
            params: list[Any] = []
            if kind:
                clauses.append("kind = ?")
                params.append(kind)
            if topic_id is not None:
                clauses.append("topic_id = ?")
                params.append(topic_id)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            cur = await db.execute(
                f"SELECT * FROM sessions {where} ORDER BY updated_at DESC",
                params,
            )
            rows = await cur.fetchall()
            return [_row_to_session(r) for r in rows]

    @classmethod
    async def list_in_topic(cls, topic_id: str) -> list[Session]:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM sessions WHERE topic_id = ? ORDER BY updated_at DESC",
                (topic_id,),
            )
            rows = await cur.fetchall()
            return [_row_to_session(r) for r in rows]

    @classmethod
    async def update(
        cls,
        session_id: str,
        *,
        title: str | None = None,
        status: str | None = None,
        workdir: str | None = None,
        metadata: dict[str, Any] | None = None,
        touch: bool = True,
    ) -> Session | None:
        sets: list[str] = []
        params: list[Any] = []
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if workdir is not None:
            sets.append("workdir = ?")
            params.append(workdir)
        if metadata is not None:
            sets.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))
        if touch:
            sets.append("updated_at = datetime('now')")
        if not sets:
            return await cls.get(session_id)
        params.append(session_id)
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                f"UPDATE sessions SET {', '.join(sets)} WHERE id = ?", params
            )
            await db.commit()
        return await cls.get(session_id)

    @classmethod
    async def delete(cls, session_id: str) -> bool:
        async with aiosqlite.connect(get_db_path()) as db:
            cur = await db.execute(
                "DELETE FROM sessions WHERE id = ?", (session_id,)
            )
            await db.commit()
            return cur.rowcount > 0

    @classmethod
    async def delete_in_topic(cls, topic_id: str) -> int:
        async with aiosqlite.connect(get_db_path()) as db:
            cur = await db.execute(
                "DELETE FROM sessions WHERE topic_id = ?", (topic_id,)
            )
            await db.commit()
            return cur.rowcount

topic_store = TopicStore()
session_store = SessionStore()
logger.debug("topic/session stores ready")
