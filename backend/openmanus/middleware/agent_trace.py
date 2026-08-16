from __future__ import annotations

from langchain.agents.middleware.types import AgentMiddleware
from typing import Any

from openmanus.log import logger


def _short(text: Any, n: int = 120) -> str:
    s = str(text).replace("\n", " ").strip()
    return s[:n] + ("…" if len(s) > n else "")

class AgentTraceMiddleware(AgentMiddleware[Any, Any, Any]):

    def __init__(self, *, name: str = "?") -> None:
        self._name = name

    async def awrap_model_call(self, request, handler):
        result = await handler(request)
        try:
            msg = None
            if hasattr(result, "message"):
                msg = result.message
            elif hasattr(result, "choices") and result.choices:
                msg = result.choices[0].get("message") if isinstance(result.choices[0], dict) else None
            if msg is not None:
                content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "")
                text = _short(content)
                tcs = getattr(msg, "tool_calls", None) or (msg.get("tool_calls") if isinstance(msg, dict) else None)
                tc_names = [t.get("name", "?") if isinstance(t, dict) else getattr(t, "name", "?") for t in (tcs or [])]
                logger.warning("[TRACE] %s MODEL → text=%r tools=%s", self._name, text, tc_names)
            else:
                logger.warning("[TRACE] %s MODEL → (no message extracted)", self._name)
        except Exception:
            logger.warning("[TRACE] %s MODEL → (extract failed)", self._name)
        return result

    async def awrap_tool_call(self, request, handler):
        name = "?"
        tc = getattr(request, "tool_call", None)
        if isinstance(tc, dict):
            name = tc.get("name", "?")
        elif tc is not None:
            name = getattr(tc, "name", "?")
        result = await handler(request)
        try:
            content = getattr(result, "content", None) or ""
            logger.warning("[TRACE] %s TOOL %s → %s", self._name, name, _short(content))
        except Exception:
            logger.warning("[TRACE] %s TOOL %s → (done)", self._name, name)
        return result
