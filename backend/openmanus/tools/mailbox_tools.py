from __future__ import annotations

from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langchain_core.tools.base import InjectedToolArg
from pydantic import BaseModel, Field

from openmanus.topics.mailbox_store import mailbox_store

def _config_agent_name(config: RunnableConfig | None) -> str:
    return ((config or {}).get("configurable") or {}).get("agent_name") or "unknown"

def _config_topic_id(config: RunnableConfig | None) -> str:
    tid = ((config or {}).get("configurable") or {}).get("topic_id")
    return tid or "main"

def make_send_message_tool() -> BaseTool:
    class SendMessageInput(BaseModel):
        to_agent: str = Field(description="Name of the agent to message.")
        content: str = Field(description="The message text.")

    @tool("send_message", args_schema=SendMessageInput)
    async def send_message(
        to_agent: str,
        content: str,
        config: Annotated[RunnableConfig, InjectedToolArg] = None,
    ) -> str:
        """Send a short chat message to another agent in your team."""
        await mailbox_store.send(
            topic_id=_config_topic_id(config),
            from_agent=_config_agent_name(config),
            to_agent=to_agent,
            kind="chat",
            content=content,
        )
        return f"Sent message to {to_agent}."

    return send_message

def make_read_mailbox_tool() -> BaseTool:
    @tool("read_mailbox")
    async def read_mailbox(
        unread_only: bool = False,
        config: Annotated[RunnableConfig, InjectedToolArg] = None,
    ) -> str:
        """Read messages in your inbox (tasks, peer chat, results)."""
        msgs = await mailbox_store.inbox(
            _config_topic_id(config), _config_agent_name(config), unread_only=unread_only
        )
        if not msgs:
            return "Inbox empty."
        lines = []
        for m in msgs:
            tail = m.content or ""
            if m.whiteboard_ref:
                tail += f" (whiteboard: {m.whiteboard_ref})"
            lines.append(f"[{m.kind}] from {m.from_agent}: {tail}")
        return "Inbox:\n" + "\n".join(lines)

    return read_mailbox
