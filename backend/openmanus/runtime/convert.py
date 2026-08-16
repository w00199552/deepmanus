from __future__ import annotations

import uuid
from typing import Any

from openmanus.runtime.event_schema import ev_message_end


def _new_id() -> str:
    return uuid.uuid4().hex

def _extract_text(content: Any) -> list[str]:
    if content is None:
        return []
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if t:
                    out.append(t)
            elif isinstance(block, str):
                out.append(block)
        return out
    return []

def extract_reasoning(msg: Any) -> list[str]:
    ak = getattr(msg, "additional_kwargs", None) or {}
    rc = ak.get("reasoning_content")
    if isinstance(rc, str) and rc:
        return [rc]
    if isinstance(rc, list):
        out = [p.get("text", "") if isinstance(p, dict) else str(p) for p in rc]
        return [s for s in out if s]
    content = getattr(msg, "content", None)
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in ("thinking", "reasoning"):
                t = block.get("thinking") or block.get("text")
                if t:
                    out.append(t)
        return out
    return []

class StreamState:

    def __init__(self) -> None:
        self.assistant_message_id: str | None = None
        self.message_open: bool = False
        self.open_tool_calls: set[str] = set()
        self.open_steps: set[str] = set()

    def close_turn(self, *, session_id: str, speaker: str) -> list[str]:
        frames: list[str] = []
        if self.message_open and self.assistant_message_id:
            frames.append(ev_message_end(
                session_id=session_id,
                message_id=self.assistant_message_id,
                speaker=speaker,
            ))
        self.assistant_message_id = None
        self.message_open = False
        return frames

def convert_chunk(chunk, st: StreamState, *, session_id: str, speaker: str) -> list[str]:
    from langchain_core.messages import AIMessageChunk, ToolMessage

    from openmanus.runtime import event_schema as E

    ctype = chunk.get("type")
    frames: list[str] = []

    if ctype == "updates":
        for node_name in (chunk.get("data") or {}).keys():
            if not node_name:
                continue
            if node_name not in st.open_steps:
                st.open_steps.add(node_name)
                frames.append(E.frame(E.ev_step_start(session_id=session_id, node=node_name)))
            frames.append(E.frame(E.ev_step_end(session_id=session_id, node=node_name)))
        return frames

    if ctype != "messages":
        return []

    data = chunk.get("data")
    if not isinstance(data, tuple) or len(data) != 2:
        return []
    msg, _meta = data

    if isinstance(msg, AIMessageChunk):
        chunk_msg_id = getattr(msg, "id", None) or None

        for tc in msg.tool_call_chunks or []:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None)
            tcid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
            if name:
                tcid = tcid or _new_id()
                st.open_tool_calls.add(tcid)
                if st.assistant_message_id is None:
                    st.assistant_message_id = chunk_msg_id or _new_id()
                frames.append(E.frame(E.ev_tool_call_start(
                    session_id=session_id, message_id=st.assistant_message_id,
                    speaker=speaker, call_id=tcid, tool=name,
                )))
            if args:
                if not tcid:
                    tcid = next(iter(st.open_tool_calls), None) or _new_id()
                frames.append(E.frame(E.ev_tool_call_args(
                    session_id=session_id, call_id=tcid, args_json=str(args),
                )))

        for thought in extract_reasoning(msg):
            if not thought:
                continue
            if st.assistant_message_id is None:
                st.assistant_message_id = chunk_msg_id or _new_id()
            frames.append(E.frame(E.ev_thinking_delta(
                session_id=session_id, message_id=st.assistant_message_id,
                speaker=speaker, delta=thought,
            )))

        for text in _extract_text(msg.content):
            if not text:
                continue
            if not st.message_open:
                if st.assistant_message_id is None:
                    st.assistant_message_id = chunk_msg_id or _new_id()
                frames.append(E.frame(E.ev_message_start(
                    session_id=session_id, message_id=st.assistant_message_id, speaker=speaker,
                )))
                st.message_open = True
            frames.append(E.frame(E.ev_text_delta(
                session_id=session_id, message_id=st.assistant_message_id,
                speaker=speaker, delta=text,
            )))
        return frames

    if isinstance(msg, ToolMessage):
        tcid = getattr(msg, "tool_call_id", None) or _new_id()
        try:
            content = str(msg.content)
        except Exception:
            content = "<tool result>"
        st.open_tool_calls.discard(tcid)
        frames.append(E.frame(E.ev_tool_call_result(
            session_id=session_id, call_id=tcid, result=content,
        )))
        frames.append(E.frame(E.ev_tool_call_end(
            session_id=session_id, call_id=tcid,
        )))
        frames.extend(st.close_turn(session_id=session_id, speaker=speaker))
        return frames

    return []

def close_open(st: StreamState, *, session_id: str, speaker: str) -> list[str]:
    from openmanus.runtime import event_schema as E

    frames: list[str] = []
    if st.message_open:
        frames.append(E.frame(E.ev_message_end(
            session_id=session_id, message_id=st.assistant_message_id or _new_id(),
            speaker=speaker,
        )))
        st.message_open = False
    for tcid in list(st.open_tool_calls):
        frames.append(E.frame(E.ev_tool_call_end(session_id=session_id, call_id=tcid)))
        st.open_tool_calls.discard(tcid)
    return frames
