from __future__ import annotations

import aiosqlite
import asyncio
from typing import Awaitable, Callable

from openmanus.common.exceptions import ValidationError
from openmanus.db import get_db_path
from openmanus.log import logger
from openmanus.topics.entities import MailboxMessage

_channel_pusher: Callable[[str, str, MailboxMessage], Awaitable[None]] | None = None

_wakeup_callback: Callable[[str, str], Awaitable[None]] | None = None

def set_channel_pusher(pusher: Callable[[str, str, MailboxMessage], Awaitable[None]]) -> None:
    global _channel_pusher
    _channel_pusher = pusher

def set_wakeup_callback(cb: Callable[[str, str], Awaitable[None]]) -> None:
    global _wakeup_callback
    _wakeup_callback = cb

KIND_DISPATCH = "dispatch"
KIND_RESULT = "result"
KIND_CHAT = "chat"
_VALID_KINDS = {KIND_DISPATCH, KIND_RESULT, KIND_CHAT}

def _row_to_mailbox(row: aiosqlite.Row) -> MailboxMessage:
    return MailboxMessage(
        id=row["id"],
        topic_id=row["topic_id"],
        from_agent=row["from_agent"],
        to_agent=row["to_agent"],
        kind=row["kind"],
        content=row["content"],
        whiteboard_ref=row["whiteboard_ref"],
        read=bool(row["read"]),
        created_at=row["created_at"],
    )

class MailboxStore:

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, topic_id: str, agent_name: str) -> asyncio.Lock:
        key = f"{topic_id}:{agent_name}"
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def send(
        self,
        *,
        topic_id: str,
        from_agent: str,
        to_agent: str,
        kind: str,
        content: str | None = None,
        whiteboard_ref: str | None = None,
    ) -> MailboxMessage:
        if kind not in _VALID_KINDS:
            raise ValidationError(
                f"invalid mailbox kind {kind!r}; expected one of {_VALID_KINDS}"
            )

        lock = self._get_lock(topic_id, to_agent)
        async with lock:
            async with aiosqlite.connect(get_db_path()) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    """INSERT INTO mailboxes
                       (topic_id, from_agent, to_agent, kind, content, whiteboard_ref)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (topic_id, from_agent, to_agent, kind, content, whiteboard_ref),
                )
                msg_id = cur.lastrowid
                await db.commit()
                cur = await db.execute(
                    "SELECT * FROM mailboxes WHERE id = ?", (msg_id,)
                )
                row = await cur.fetchone()
            msg = _row_to_mailbox(row)

            if _channel_pusher is not None:
                try:
                    await _channel_pusher(topic_id, to_agent, msg)
                except Exception:
                    logger.exception(
                        "mailbox live-push failed for %s/%s", topic_id, to_agent
                    )
            if _wakeup_callback is not None:
                try:
                    await _wakeup_callback(topic_id, to_agent)
                except Exception:
                    logger.exception(
                        "mailbox wake-up failed for %s/%s", topic_id, to_agent
                    )
        return msg

    async def inbox(
        self, topic_id: str, agent_name: str, unread_only: bool = False
    ) -> list[MailboxMessage]:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            where = "WHERE topic_id = ? AND to_agent = ?"
            if unread_only:
                where += " AND read = 0"
            cur = await db.execute(
                f"SELECT * FROM mailboxes {where} ORDER BY created_at ASC, id ASC",
                (topic_id, agent_name),
            )
            rows = await cur.fetchall()
            return [_row_to_mailbox(r) for r in rows]

    async def mark_read(
        self, topic_id: str, agent_name: str, msg_ids: list[int]
    ) -> None:
        if not msg_ids:
            return
        placeholders = ",".join("?" * len(msg_ids))
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                f"UPDATE mailboxes SET read = 1 "
                f"WHERE topic_id = ? AND to_agent = ? AND id IN ({placeholders})",
                (topic_id, agent_name, *msg_ids),
            )
            await db.commit()

    async def check_and_drain(
        self,
        topic_id: str,
        agent_name: str,
        on_messages: Callable[[list[MailboxMessage]], Awaitable[None]],
    ) -> None:
        lock = self._get_lock(topic_id, agent_name)
        async with lock:
            msgs = await self.inbox(topic_id, agent_name, unread_only=True)
            if not msgs:
                return
            await self.mark_read(topic_id, agent_name, [m.id for m in msgs])
            try:
                await on_messages(msgs)
            except Exception:
                logger.exception(
                    "mailbox drain on_messages failed for %s/%s",
                    topic_id,
                    agent_name,
                )

    async def delete_in_topic(self, topic_id: str) -> int:
        async with aiosqlite.connect(get_db_path()) as db:
            cur = await db.execute(
                "DELETE FROM mailboxes WHERE topic_id = ?", (topic_id,)
            )
            await db.commit()
            return cur.rowcount

mailbox_store = MailboxStore()
