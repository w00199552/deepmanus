from __future__ import annotations

import asyncio
from typing import AsyncIterator

from openmanus.log import logger
from openmanus.runtime.event_schema import done_sentinel, frame, is_done_sentinel
from openmanus.topics.entities import MailboxMessage
from openmanus.topics.mailbox_store import mailbox_store, set_channel_pusher
from openmanus.topics.store import session_store

class ChannelRegistry:

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
        self._finished: set[str] = set()

    def get_queue(self, session_id: str) -> asyncio.Queue:
        q = self._queues.get(session_id)
        if q is None:
            q = asyncio.Queue()
            self._queues[session_id] = q
        return q

    def has(self, session_id: str) -> bool:
        return session_id in self._queues

    def discard(self, session_id: str) -> None:
        self._queues.pop(session_id, None)
        self._finished.discard(session_id)

    def mark_finished(self, session_id: str) -> None:
        self._finished.add(session_id)

    def is_finished(self, session_id: str) -> bool:
        return session_id in self._finished

    async def _push_live(self, topic_id: str, to_agent: str, msg: MailboxMessage) -> None:
        try:
            members = await session_store.list_in_topic(topic_id)
        except Exception:
            return
        for s in members:
            if s.name != to_agent:
                continue
            sid = s.id
            if not self.has(sid):
                continue
            ev = {
                "kind": "mailbox",
                "session_id": sid,
                "mailbox": msg.model_dump(),
            }
            await self.get_queue(sid).put(frame(ev))

channels = ChannelRegistry()

set_channel_pusher(channels._push_live)

async def drain_single(queue: asyncio.Queue) -> AsyncIterator[str]:
    while True:
        item = await queue.get()
        if is_done_sentinel(item):
            yield "data: [DONE]\n\n"
            return
        yield item

async def drain_sessions(
    session_ids: list[str],
    *,
    stop_when_done: set[str] | None = None,
) -> AsyncIterator[str]:
    gate = set(stop_when_done) if stop_when_done else set(session_ids)
    seen_done: set[str] = set()
    active = set(session_ids)

    while active:
        tasks: dict[asyncio.Task, str] = {}
        for sid in list(active):
            tasks[asyncio.ensure_future(channels.get_queue(sid).get())] = sid
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            sid = tasks[t]
            item = t.result()
            if is_done_sentinel(item):
                seen_done.add(sid)
                continue
            yield item
        for t in pending:
            t.cancel()
        if gate and gate <= seen_done:
            break
        if not gate and active <= seen_done:
            break

    yield "data: [DONE]\n\n"

async def fan_in(
    topic_id: str | None,
    focus_session_id: str | None = None,
) -> AsyncIterator[str]:
    if topic_id is None and focus_session_id is not None:
        async for f in drain_single(channels.get_queue(focus_session_id)):
            yield f
        return

    if topic_id is None:
        yield "data: [DONE]\n\n"
        return

    known: set[str] = set()
    if focus_session_id:
        known.add(focus_session_id)
    focus_done = False
    all_done = False

    while (focus_session_id and not focus_done) or (not focus_session_id and not all_done):
        members = await session_store.list_in_topic(topic_id)
        known.update(s.id for s in members)

        if not known:
            await asyncio.sleep(1)
            continue

        tasks: dict[asyncio.Task, str] = {}
        for sid in known:
            tasks[asyncio.ensure_future(channels.get_queue(sid).get())] = sid
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            sid = tasks[t]
            item = t.result()
            if is_done_sentinel(item):
                if sid == focus_session_id:
                    focus_done = True
                continue
            yield item
        for t in pending:
            t.cancel()
        if not focus_session_id:
            seen_done = {sid for sid in known if channels.is_finished(sid)}
            if known and seen_done == known:
                all_done = True

    yield "data: [DONE]\n\n"
