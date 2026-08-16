from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

BACKEND_ROOT = Path(__file__).resolve().parent.parent
SEED_AGENTS_DIR = BACKEND_ROOT / "seed" / "agents"

def _read_seed_agents() -> dict[str, Any]:
    configs: dict[str, Any] = {}
    for agent_dir in sorted(SEED_AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        yaml_path = agent_dir / "agent.yaml"
        if not yaml_path.exists():
            continue
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        prompt = ""
        pf = raw.get("prompt_file", "prompt.md")
        pp = agent_dir / pf
        if pp.exists():
            prompt = pp.read_text(encoding="utf-8")
        from openmanus.agents.entities import Agent

        name = raw.get("name") or agent_dir.name
        configs[name] = Agent(
            name=name,
            prompt=prompt,
            description=raw.get("description", ""),
            tools=raw.get("tools", []),
            skills=raw.get("skills", []),
            sub_agents=raw.get("sub_agents", []),
            is_builtin=raw.get("is_builtin", False),
        )
    return configs

@pytest.fixture
def tmp_openmanus_home(tmp_path, monkeypatch):
    home = tmp_path / "openmanus_home"
    (home / "agents").mkdir(parents=True)
    (home / "tools").mkdir(parents=True)
    (home / "skills").mkdir(parents=True)
    monkeypatch.setenv("OPENMANUS_HOME", str(home))
    return home

@pytest.fixture
def seed_agents_in_loader():
    from openmanus.agents.loader import agent_loader

    saved = dict(agent_loader._configs)
    agent_loader._configs = _read_seed_agents()
    try:
        yield agent_loader
    finally:
        agent_loader._configs = saved
