from __future__ import annotations

import asyncio
from langchain_core.messages import HumanMessage

from openmanus.log import logger
from openmanus.runtime import event_schema as E
from openmanus.runtime.channels import channels
from openmanus.runtime.convert import StreamState, close_open, convert_chunk
from openmanus.topics.mailbox_store import mailbox_store, set_wakeup_callback
from openmanus.topics.store import session_store
from openmanus.topics.whiteboard_store import whiteboard_store


async def _final_text(agent, config) -> str:
    try:
        snapshot = await agent.aget_state(config)
        for msg in reversed(getattr(snapshot, "values", {}).get("messages", [])):
            if getattr(msg, "type", "") == "ai":
                content = getattr(msg, "content", "")
                if isinstance(content, list):
                    content = " ".join(
                        p.get("text", "") if isinstance(p, dict) else str(p)
                        for p in content
                    )
                return str(content) or "(no output)"
    except Exception:
        logger.exception("failed reading final state")
    return "(no output)"

class StreamEngine:

    def __init__(self) -> None:
        self._pending: dict[str, list] = {}
        self._tasks: set = set()

    async def run(
        self,
        *,
        session_id: str,
        prompt: str,
        speaker: str,
        mode: str = "async",
    ) -> str | None:
        if mode == "async":
            task = asyncio.create_task(
                self._stream(
                    session_id=session_id, prompt=prompt,
                    speaker=speaker,
                )
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return None
        return await self._stream(
            session_id=session_id, prompt=prompt,
            speaker=speaker,
        )

    async def start(
        self,
        *,
        caller_session_id: str,
        target_agent: str,
        task: str,
        topic_id: str,
        target_session_id: str,
    ) -> str:
        prompt = task

        self._pending.setdefault(caller_session_id, []).append({
            "target_session_id": target_session_id,
            "prompt": prompt, "speaker": target_agent,
            "topic_id": topic_id, "caller_session_id": caller_session_id,
        })
        return target_session_id

    async def _stream(
        self, *, session_id: str, prompt: str, speaker: str,
    ) -> str:
        from openmanus.agents.agent_factory import build_agent, close_agent

        agent, ctx = await build_agent(session_id)
        queue = channels.get_queue(session_id)
        st = StreamState()
        config = ctx.to_config()
        await session_store.update(session_id, status="running", touch=True)
        final = "(no output)"
        try:
            async for chunk in agent.astream(
                {"messages": [HumanMessage(content=prompt)]},
                config=config,
                stream_mode=["messages", "updates"],
                subgraphs=False,
                version="v2",
            ):
                for f in convert_chunk(chunk, st, session_id=session_id, speaker=speaker):
                    await queue.put(f)
            for f in close_open(st, session_id=session_id, speaker=speaker):
                await queue.put(f)
            await session_store.update(session_id, status="active", touch=True)
            await queue.put(E.frame(E.ev_done(session_id=session_id)))
            final = await _final_text(agent, config)
        except Exception as exc:
            logger.exception("engine failed for session %s", session_id)
            for f in close_open(st, session_id=session_id, speaker=speaker):
                await queue.put(f)
            await queue.put(E.frame(E.ev_error(session_id=session_id, message=str(exc))))
            await session_store.update(session_id, status="error", touch=True)
            await queue.put(E.frame(E.ev_done(session_id=session_id)))
        finally:
            await close_agent(agent)
            await queue.put(E.done_sentinel(session_id))
            channels.mark_finished(session_id)
            pending = self._pending.pop(session_id, [])
            for p in pending:
                task = asyncio.create_task(self._start_and_record(
                    target_session_id=p["target_session_id"],
                    prompt=p["prompt"], speaker=p["speaker"],
                    topic_id=p["topic_id"], caller_session_id=p["caller_session_id"],
                ))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            await self._drain_and_start_session(ctx.topic_id, ctx.agent_name)
        return final

    async def _start_and_record(
        self, *, target_session_id: str, prompt: str, speaker: str,
        topic_id: str, caller_session_id: str,
    ) -> None:
        answer = await self._stream(
            session_id=target_session_id, prompt=prompt, speaker=speaker,
        )
        await self._record_result(
            topic_id=topic_id, target_session_id=target_session_id,
            caller_session_id=caller_session_id, target_agent=speaker, answer=answer or "",
        )

    async def _record_result(
        self, *, topic_id: str, target_session_id: str,
        caller_session_id: str, target_agent: str, answer: str,
    ) -> None:
        caller = await session_store.get(caller_session_id)
        if caller and caller.kind == "root":
            return
        if not topic_id:
            return
        caller_name = caller.name if caller else "unknown"
        try:
            art = await whiteboard_store.create(
                topic_id=topic_id, author=target_agent,
                kind="result", status="finished",
                title=f"{target_agent} result",
                content=answer[:2000] or "(no output)",
            )
            await mailbox_store.send(
                topic_id=topic_id,
                from_agent=target_agent, to_agent=caller_name,
                kind="result",
                content=f"{target_agent} finished",
                whiteboard_ref=art.id,
            )
        except Exception:
            logger.exception("failed recording result for %s", target_session_id)

    async def _wakeup(self, topic_id: str, agent_name: str) -> None:
        sessions = await session_store.list_in_topic(topic_id)
        agent_sessions = [s for s in sessions if s.name == agent_name]
        if not agent_sessions:
            return
        latest = agent_sessions[0]
        if latest.status == "running":
            return
        await self._drain_and_start_session(topic_id, agent_name)

    async def _drain_and_start_session(self, topic_id: str, agent_name: str) -> None:
        async def on_messages(msgs):
            lines = []
            for m in msgs:
                sender = m.from_agent
                lines.append(f"- from {sender}: {m.content or ''}")
            prompt = ("你收到了以下新消息:\n" + "\n".join(lines)
                      + "\n\n请读取并处理。")
            session = await session_store.create(
                topic_id=topic_id, kind="subagent", name=agent_name,
                title=f"{agent_name} mailbox",
            )
            await session_store.update(session.id, status="running")
            task = asyncio.create_task(self._stream(
                session_id=session.id, prompt=prompt, speaker=agent_name,
            ))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        await mailbox_store.check_and_drain(topic_id, agent_name, on_messages)

engine = StreamEngine()

set_wakeup_callback(engine._wakeup)
