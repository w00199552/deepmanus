from __future__ import annotations

import uuid

import aiosqlite

from openmanus.db import get_db_path
from openmanus.topics.entities import WhiteboardNote

def _row_to_note(row: aiosqlite.Row) -> WhiteboardNote:
    return WhiteboardNote(
        id=row["id"],
        topic_id=row["topic_id"],
        author=row["author"],
        kind=row["kind"],
        status=row["status"],
        title=row["title"],
        content=row["content"],
        created_at=row["created_at"],
    )

class WhiteboardStore:

    @classmethod
    async def create(
        cls,
        *,
        topic_id: str,
        author: str,
        kind: str = "task",
        status: str = "pending",
        title: str | None = None,
        content: str | None = None,
        note_id: str | None = None,
    ) -> WhiteboardNote:
        nid = note_id or uuid.uuid4().hex
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                """INSERT INTO whiteboard_note
                       (id, topic_id, author, kind, status, title, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (nid, topic_id, author, kind, status, title, content),
            )
            await db.commit()
        created = await cls.get(nid)
        assert created is not None
        return created

    @classmethod
    async def get(cls, note_id: str) -> WhiteboardNote | None:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM whiteboard_note WHERE id = ?", (note_id,)
            )
            row = await cur.fetchone()
            return _row_to_note(row) if row else None

    @classmethod
    async def list_in_topic(
        cls,
        topic_id: str,
        status: str | None = None,
    ) -> list[WhiteboardNote]:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cur = await db.execute(
                    "SELECT * FROM whiteboard_note "
                    "WHERE topic_id = ? AND status = ? "
                    "ORDER BY created_at DESC",
                    (topic_id, status),
                )
            else:
                cur = await db.execute(
                    "SELECT * FROM whiteboard_note "
                    "WHERE topic_id = ? "
                    "ORDER BY created_at DESC",
                    (topic_id,),
                )
            rows = await cur.fetchall()
            return [_row_to_note(r) for r in rows]

    @classmethod
    async def update_status(cls, note_id: str, status: str) -> WhiteboardNote | None:
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                "UPDATE whiteboard_note SET status = ? WHERE id = ?",
                (status, note_id),
            )
            await db.commit()
        return await cls.get(note_id)

    @classmethod
    async def delete(cls, note_id: str) -> bool:
        async with aiosqlite.connect(get_db_path()) as db:
            cur = await db.execute(
                "DELETE FROM whiteboard_note WHERE id = ?", (note_id,)
            )
            await db.commit()
            return cur.rowcount > 0

    @classmethod
    async def delete_in_topic(cls, topic_id: str) -> int:
        async with aiosqlite.connect(get_db_path()) as db:
            cur = await db.execute(
                "DELETE FROM whiteboard_note WHERE topic_id = ?", (topic_id,)
            )
            await db.commit()
            return cur.rowcount

whiteboard_store = WhiteboardStore()
