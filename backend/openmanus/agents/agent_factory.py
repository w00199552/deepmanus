from __future__ import annotations

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
from typing import Any

from openmanus.agents.loader import agent_loader
from openmanus.common.exceptions import AgentError, NotFoundError
from openmanus.config import settings
from openmanus.llm import ChatGLM
from openmanus.log import logger
from openmanus.memory import get_checkpointer
from openmanus.middleware.agent_trace import AgentTraceMiddleware
from openmanus.middleware.retry import build_retry_middlewares
from openmanus.middleware.tool_guard import ToolGuardMiddleware
from openmanus.sandbox.readonly_backend import ReadOnlyFilesystemBackend
from openmanus.skills.loader import SKILLS_DIR
from openmanus.tools.dispatch_tool import make_dispatch_tool
from openmanus.tools.mailbox_tools import make_read_mailbox_tool, make_send_message_tool
from openmanus.tools.tool_loader import tool_loader
from openmanus.tools.whiteboard_tool import (
    make_whiteboard_read_tool,
    make_whiteboard_update_status_tool,
    make_whiteboard_write_tool,
)
from openmanus.topics.store import session_store, topic_store

BUILTIN_TOOLS = frozenset(
    {"write_todos", "ls", "read_file", "write_file", "edit_file",
     "glob", "grep", "execute", "task"}
)

_default_model: BaseChatModel | None = None


def _build_model() -> BaseChatModel:
    provider = settings.model_provider.lower()
    import httpx

    sync_http = httpx.Client(verify=settings.ssl_verify, trust_env=False)
    async_http = httpx.AsyncClient(verify=settings.ssl_verify, trust_env=False)

    if provider == "anthropic":
        return ChatAnthropic(
            model=settings.model,
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
            streaming=True,
            max_tokens=8192,
        )
    return ChatGLM(
        model=settings.model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        streaming=True,
        http_client=sync_http,
        http_async_client=async_http,
        default_headers={"x-reasoning-format": "reasoning"}
    )


def _build_backend(workdir: str) -> LocalShellBackend:
    return LocalShellBackend(root_dir=workdir, virtual_mode=True, inherit_env=True)


def compute_thread_id(topic_id: str, agent_name: str) -> str:
    return f"{topic_id}:{agent_name}"


class AgentContext(BaseModel):
    session_id: str = Field(description="执行 ID")
    topic_id: str = Field(description="所属 topic ID")
    agent_name: str = Field(description="agent 角色名")
    thread_id: str = Field(description="checkpointer 记忆链键")
    workdir: str = Field(description="工作目录")

    def to_config(self) -> dict[str, Any]:
        return {"configurable": {
            "thread_id": self.thread_id,
            "session_id": self.session_id,
            "topic_id": self.topic_id,
            "agent_name": self.agent_name,
        }}


def resolve_session_id(config: Any) -> str:
    try:
        return ((config or {}).get("configurable") or {}).get("session_id") or "unknown"
    except Exception:
        return "unknown"


def resolve_topic_id(config: Any) -> str | None:
    try:
        tid = ((config or {}).get("configurable") or {}).get("topic_id")
        return tid if tid else None
    except Exception:
        return None


def resolve_agent_name(config: Any) -> str:
    try:
        return ((config or {}).get("configurable") or {}).get("agent_name") or "unknown"
    except Exception:
        return "unknown"


def resolve_tool_whitelist(declared: list[str] | set[str]) -> tuple[frozenset[str], frozenset[str], list[str]]:
    declared_set = set(declared)
    builtin_kept = declared_set & BUILTIN_TOOLS
    builtin_excluded = BUILTIN_TOOLS - builtin_kept
    extra_tool_names = sorted(declared_set - BUILTIN_TOOLS)
    return frozenset(builtin_kept), frozenset(builtin_excluded), extra_tool_names


def _build_tools(tool_names: list[str], workdir: str, agent_name: str = "") -> list:
    tools: list = []
    for tname in tool_names:
        if tname == "dispatch":
            tools.append(make_dispatch_tool(workdir=workdir))
        elif tname == "send_message":
            tools.append(make_send_message_tool())
        elif tname == "read_mailbox":
            tools.append(make_read_mailbox_tool())
        elif tname == "whiteboard_write":
            tools.append(make_whiteboard_write_tool(
                topic_id_fn=resolve_topic_id, author_fn=resolve_agent_name,
            ))
        elif tname == "whiteboard_update_status":
            tools.append(make_whiteboard_update_status_tool())
        elif tname == "whiteboard_read":
            tools.append(make_whiteboard_read_tool(topic_id_fn=resolve_topic_id))
        else:
            user_tool = tool_loader.get(tname)
            if user_tool is not None:
                tools.append(user_tool)
            else:
                logger.warning("unknown tool '%s' for agent '%s', skipping", tname, agent_name)
    return tools


def _resolve_prompt(raw_prompt: str, self_name: str) -> str:
    if "{{AGENTS}}" not in raw_prompt:
        return raw_prompt

    lines = []
    for agent_name in sorted(agent_loader.all_names()):
        if agent_name == self_name:
            continue
        agent_cfg = agent_loader.get(agent_name)
        if agent_cfg is None:
            continue
        desc = agent_cfg.description.strip()
        if desc:
            lines.append(f"- {agent_name}: {desc}")
        else:
            lines.append(f"- {agent_name}")

    return raw_prompt.replace("{{AGENTS}}", "\n".join(lines))


async def build_agent(session_id: str) -> tuple[CompiledStateGraph, AgentContext]:
    global _default_model
    if _default_model is None:
        _default_model = _build_model()

    s = await session_store.get(session_id)
    if not s:
        raise NotFoundError(f"session not found: {session_id}")
    name = s.name
    if not name:
        name = "TeamLeader" if s.kind == "team" else "Manus"
    topic_id = s.topic_id or "main"
    topic = await topic_store.get(topic_id)
    workdir = (topic.workdir if topic else None) or s.workdir or settings.workdir
    ctx = AgentContext(
        session_id=session_id,
        topic_id=topic_id,
        agent_name=name,
        thread_id=compute_thread_id(topic_id, name),
        workdir=workdir,
    )

    own_checkpointer = await get_checkpointer()

    cfg = agent_loader.get(name)
    if not cfg:
        raise AgentError(
            f"Unknown agent name: {name!r}. Available: {agent_loader.all_names()}"
        )

    _kept, excluded, extra_tool_names = resolve_tool_whitelist(cfg.tools)
    tools = _build_tools(extra_tool_names, workdir, agent_name=name)

    from deepagents.backends.composite import CompositeBackend

    default_backend = _build_backend(workdir)
    routes = {}
    skill_names = cfg.skills
    if skill_names and SKILLS_DIR.exists():
        routes["/skills/"] = ReadOnlyFilesystemBackend(root_dir=str(SKILLS_DIR))
    backend = CompositeBackend(default=default_backend, routes=routes) if routes else default_backend

    skill_paths = [f"/skills/{sname}/" for sname in skill_names] if skill_names else []

    agent = create_deep_agent(
        model=_default_model,
        system_prompt=_resolve_prompt(cfg.prompt, name),
        tools=tools,
        backend=backend,
        checkpointer=own_checkpointer,
        skills=skill_paths if skill_paths else None,
        middleware=[
            *build_retry_middlewares(settings),
            ToolGuardMiddleware(excluded=excluded),
            AgentTraceMiddleware(name=name),
        ],
        name=name,
    )
    return agent, ctx


async def close_agent(agent: CompiledStateGraph) -> None:
    cp = getattr(agent, "checkpointer", None)
    if cp is not None:
        conn = getattr(cp, "conn", None)
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                pass
