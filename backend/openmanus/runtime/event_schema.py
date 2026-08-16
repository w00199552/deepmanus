from __future__ import annotations

import json
from typing import Any

DONE_TYPE = "__done__"

def done_sentinel(session_id: str) -> dict[str, Any]:
    return {"type": DONE_TYPE, "session_id": session_id}

def is_done_sentinel(item: Any) -> bool:
    return isinstance(item, dict) and item.get("type") == DONE_TYPE

def frame(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

def ev_message_start(*, session_id: str, message_id: str, speaker: str) -> dict[str, Any]:
    return {"kind": "message_start", "session_id": session_id, "message_id": message_id, "speaker": speaker}

def ev_text_delta(*, session_id: str, message_id: str, speaker: str, delta: str) -> dict[str, Any]:
    return {"kind": "text_delta", "session_id": session_id, "message_id": message_id, "speaker": speaker, "delta": delta}

def ev_thinking_delta(*, session_id: str, message_id: str, speaker: str, delta: str) -> dict[str, Any]:
    return {"kind": "thinking_delta", "session_id": session_id, "message_id": message_id, "speaker": speaker, "delta": delta}

def ev_message_end(*, session_id: str, message_id: str, speaker: str) -> dict[str, Any]:
    return {"kind": "message_end", "session_id": session_id, "message_id": message_id, "speaker": speaker}

def ev_tool_call_start(*, session_id: str, message_id: str, speaker: str, call_id: str, tool: str) -> dict[str, Any]:
    return {"kind": "tool_call_start", "session_id": session_id, "message_id": message_id, "speaker": speaker, "call_id": call_id, "tool": tool}

def ev_tool_call_args(*, session_id: str, call_id: str, args_json: str) -> dict[str, Any]:
    return {"kind": "tool_call_args", "session_id": session_id, "call_id": call_id, "args_json": args_json}

def ev_tool_call_result(*, session_id: str, call_id: str, result: str) -> dict[str, Any]:
    return {"kind": "tool_call_result", "session_id": session_id, "call_id": call_id, "result": result}

def ev_tool_call_end(*, session_id: str, call_id: str) -> dict[str, Any]:
    return {"kind": "tool_call_end", "session_id": session_id, "call_id": call_id}

def ev_step_start(*, session_id: str, node: str) -> dict[str, Any]:
    return {"kind": "step_start", "session_id": session_id, "node": node}

def ev_step_end(*, session_id: str, node: str) -> dict[str, Any]:
    return {"kind": "step_end", "session_id": session_id, "node": node}

def ev_error(*, session_id: str, message: str) -> dict[str, Any]:
    return {"kind": "error", "session_id": session_id, "message": message}

def ev_done(*, session_id: str) -> dict[str, Any]:
    return {"kind": "done", "session_id": session_id}
