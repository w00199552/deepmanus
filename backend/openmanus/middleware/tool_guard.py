from __future__ import annotations

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from typing import Any, Awaitable, Callable

if __name__ != "__main__":
    pass

def _name(tool: Any) -> str | None:
    if isinstance(tool, dict):
        n = tool.get("name")
        return n if isinstance(n, str) else None
    return getattr(tool, "name", None)

class ToolGuardMiddleware(AgentMiddleware[Any, Any, Any]):

    def __init__(self, *, excluded: frozenset[str]) -> None:
        self._excluded = excluded

    def wrap_model_call(self, request, handler):
        if self._excluded:
            request = request.override(
                tools=[t for t in request.tools if _name(t) not in self._excluded]
            )
        return handler(request)

    async def awrap_model_call(self, request, handler):
        if self._excluded:
            request = request.override(
                tools=[t for t in request.tools if _name(t) not in self._excluded]
            )
        return await handler(request)

    def wrap_tool_call(self, request, handler):
        name = request.tool_call.get("name") if isinstance(request.tool_call, dict) else None
        if name in self._excluded:
            return ToolMessage(
                content=(
                    f"Tool '{name}' is not available to this agent. This is a "
                    f"router/read-only agent — delegate the work with "
                    f"dispatch_single / dispatch_to_team instead."
                ),
                tool_call_id=request.tool_call.get("id", ""),
                name=name or "blocked",
            )
        return handler(request)

    async def awrap_tool_call(self, request, handler):
        name = request.tool_call.get("name") if isinstance(request.tool_call, dict) else None
        if name in self._excluded:
            return ToolMessage(
                content=(
                    f"Tool '{name}' is not available to this agent. This is a "
                    f"router/read-only agent — delegate the work with "
                    f"dispatch_single / dispatch_to_team instead."
                ),
                tool_call_id=request.tool_call.get("id", ""),
                name=name or "blocked",
            )
        return await handler(request)
