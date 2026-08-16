from __future__ import annotations

import asyncio
import pytest
import tempfile
import unittest.mock as mk
import yaml
from pathlib import Path
from typing import Any

from openmanus.agents import agent_factory as factory_mod
from openmanus.agents.agent_factory import BUILTIN_TOOLS, resolve_tool_whitelist
from openmanus.middleware.tool_guard import ToolGuardMiddleware

SEED_TOOLS = {
    "Manus": ["dispatch"],
    "Coder": ["read_file", "write_file", "edit_file", "ls", "glob", "grep", "execute"],
    "Researcher": ["read_file", "ls", "glob", "grep"],
    "TeamLeader": [
        "dispatch", "send_message", "read_mailbox",
        "whiteboard_write", "whiteboard_read",
    ],
}

SESSION_FIXTURES = [
    ("s-manus", "Manus"),
    ("s-coder", "Coder"),
    ("s-researcher", "Researcher"),
    ("s-team", "TeamLeader"),
]

def _load_seed_configs() -> dict[str, Any]:
    seed_dir = Path(__file__).resolve().parent.parent / "seed" / "agents"
    configs: dict[str, dict[str, Any]] = {}
    for agent_dir in sorted(seed_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        raw = yaml.safe_load((agent_dir / "agent.yaml").read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        prompt = ""
        pf = raw.get("prompt_file", "prompt.md")
        pp = agent_dir / pf
        if pp.exists():
            prompt = pp.read_text(encoding="utf-8")
        from openmanus.agents.entities import Agent

        configs[raw.get("name") or agent_dir.name] = Agent(
            name=raw.get("name") or agent_dir.name,
            prompt=prompt,
            description=raw.get("description", ""),
            tools=raw.get("tools", []),
            skills=raw.get("skills", []),
            sub_agents=raw.get("sub_agents", []),
            is_builtin=raw.get("is_builtin", False),
        )
    return configs

def test_build_agent_wires_excluded_correctly():
    factory_mod.agent_loader._configs = _load_seed_configs()

    captured: list[frozenset[str]] = []
    real_init = ToolGuardMiddleware.__init__

    def spy_init(self, *, excluded):
        captured.append(frozenset(excluded))
        return real_init(self, excluded=excluded)

    from langchain_core.language_models import BaseChatModel

    class _FakeModel(BaseChatModel):
        @property
        def _llm_type(self) -> str: return "fake"

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            raise AssertionError("build should not invoke the model")

        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            raise AssertionError("build should not invoke the model")

    from langgraph.checkpoint.memory import MemorySaver

    async def _fake_get_checkpointer() -> Any:
        return MemorySaver()

    tmp = tempfile.mkdtemp()
    session_map = {
        "s-manus": ("Manus", tmp),
        "s-coder": ("Coder", tmp),
        "s-researcher": ("Researcher", tmp),
        "s-team": ("TeamLeader", tmp),
    }

    async def _fake_session_get(sid):
        from openmanus.topics.entities import Session

        if sid not in session_map:
            return None
        name, wd = session_map[sid]
        return Session(id=sid, topic_id="main", kind="root", name=name, workdir=wd)

    async def _fake_topic_get(tid):
        return None

    spy_cls = type("SpyToolGuard", (ToolGuardMiddleware,), {"__init__": spy_init})
    original_cls = factory_mod.ToolGuardMiddleware
    original_model = factory_mod._default_model
    factory_mod.ToolGuardMiddleware = spy_cls
    factory_mod._default_model = _FakeModel()

    guards: dict[str, frozenset[str]] = {}
    try:
        with mk.patch.object(factory_mod, "get_checkpointer", side_effect=_fake_get_checkpointer), \
             mk.patch.object(factory_mod, "session_store") as sess_mock:
            sess_mock.get = _fake_session_get

            for sid, agent_name in SESSION_FIXTURES:
                captured.clear()
                agent, ctx = asyncio.run(factory_mod.build_agent(sid))
                assert captured, f"ToolGuardMiddleware was not constructed for {agent_name}"
                guards[agent_name] = captured[0]
                asyncio.run(factory_mod.close_agent(agent))
    finally:
        factory_mod.ToolGuardMiddleware = original_cls
        factory_mod._default_model = original_model

    for name, tools in SEED_TOOLS.items():
        _kept, expected_excluded, _ = resolve_tool_whitelist(tools)
        actual = guards[name]
        assert actual == expected_excluded, (
            f"{name}: guard excluded={sorted(actual)} != expected={sorted(expected_excluded)}"
        )

@pytest.mark.parametrize("agent_name", list(SEED_TOOLS))
def test_seed_tools_cover_only_known_categories(agent_name):
    openmanus_builtins = {
        "dispatch", "send_message", "read_mailbox",
        "whiteboard_write", "whiteboard_read",
    }
    for tname in SEED_TOOLS[agent_name]:
        is_deepagents = tname in BUILTIN_TOOLS
        is_openmanus = tname in openmanus_builtins
        assert is_deepagents or is_openmanus, (
            f"{agent_name}.tools contains unknown tool {tname!r} — "
            f"not a deepagents builtin nor an OpenManus builtin. Typo?"
        )
