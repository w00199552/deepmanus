from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langchain_core.tools.base import InjectedToolArg
from pydantic import BaseModel, Field
from typing import Annotated

from openmanus.agents.loader import agent_loader
from openmanus.log import logger
from openmanus.topics.store import session_store, topic_store


def _resolve_session_id(config: RunnableConfig | None) -> str:
    from openmanus.agents.agent_factory import resolve_session_id as _resolve
    return _resolve(config)

class DispatchInput(BaseModel):
    target_agent: str = Field(
        description=(
            "Name of the agent to delegate to. Available agents are listed in "
            "this tool's description. Use the exact name."
        )
    )
    task: str = Field(
        description=(
            "The full task to hand off. Be detailed — this is the only context "
            "the agent receives. Include goals, file paths, constraints."
        )
    )

def _build_agent_registry() -> str:
    lines = []
    for name in sorted(agent_loader.all_names()):
        cfg = agent_loader.get(name)
        if cfg is None:
            continue
        desc = cfg.description.strip()
        if desc:
            lines.append(f"  - {name}: {desc}")
        else:
            lines.append(f"  - {name}")
    return "\n".join(lines)

def make_dispatch_tool(*, workdir: str, **_kw) -> BaseTool:

    agent_registry = _build_agent_registry()

    async def dispatch(
        target_agent: str,
        task: str,
        config: Annotated[RunnableConfig, InjectedToolArg] = None,
    ) -> str:
        """Delegate a task to another agent. Returns immediately; the agent
        runs in the background. Check read_mailbox later for the result.

        Available agents (use the exact name as target_agent):
        """
        if not agent_loader.get(target_agent):
            return f"Unknown agent '{target_agent}'. Available: {', '.join(agent_loader.all_names())}."
        from openmanus.runtime.engine import engine

        caller_session_id = _resolve_session_id(config)
        caller_row = await session_store.get(caller_session_id)
        caller_topic_id = caller_row.topic_id if caller_row else None
        caller_workdir = (caller_row.workdir if caller_row else None) or workdir

        if target_agent.lower() == "teamleader":
            topic = await topic_store.create(
                title=task[:60] or "team task", workdir=caller_workdir,
            )
            team = await session_store.create(
                kind="team",
                name=target_agent,
                title=task[:60] or "team task",
                workdir=caller_workdir,
                topic_id=topic.id,
                metadata={
                    "parent": caller_session_id,
                    "members": ["TeamLeader", "Researcher", "Coder"],
                },
            )
            team_id = team.id
            await session_store.update(team_id, status="running")
            await engine.run(
                session_id=team_id, prompt=task,
                speaker=target_agent, mode="async",
            )
            return (
                f"Delegated to team {team_id}. The team is working in the "
                f"background. Tell the user they can open team {team_id[:12]}."
            )

        if caller_row is not None and caller_row.kind == "root":
            topic = await topic_store.create(
                title=task[:60] or f"{target_agent} task", workdir=caller_workdir,
            )
            topic_id = topic.id
        else:
            topic_id = caller_topic_id

        child = await session_store.create(
            kind="subagent",
            name=target_agent,
            title=task[:60] or f"{target_agent} task",
            workdir=caller_workdir,
            topic_id=topic_id,
            metadata={
                "role": target_agent,
                "parent": caller_session_id,
            },
        )
        child_id = child.id

        await engine.start(
            caller_session_id=caller_session_id,
            target_agent=target_agent,
            task=task,
            topic_id=topic_id,
            target_session_id=child_id,
        )
        return (
            f"Delegated to {target_agent} (task {child_id[:12]}), running in the "
            f"background. Use read_mailbox later to check the result."
        )

    dispatch.__doc__ = (dispatch.__doc__ or "") + agent_registry
    return tool("dispatch", args_schema=DispatchInput)(dispatch)
