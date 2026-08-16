from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from openmanus.agents import avatar
from openmanus.agents.entities import Agent
from openmanus.common.exceptions import AgentError
from openmanus.log import logger

OPENMANUS_HOME = Path(os.environ.get("OPENMANUS_HOME", Path.home() / ".openmanus"))
AGENTS_DIR = OPENMANUS_HOME / "agents"

_SEED_DIR = Path(__file__).resolve().parent.parent.parent / "seed" / "agents"

class AgentLoader:

    def __init__(self, agents_dir: Path | None = None) -> None:
        self._dir = agents_dir or AGENTS_DIR
        self._configs: dict[str, Agent] = {}

    @property
    def dir(self) -> Path:
        return self._dir

    def seed_builtin(self) -> None:
        if not _SEED_DIR.exists():
            logger.warning("seed 目录 %s 不存在 — 跳过播种", _SEED_DIR)
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        for entry in sorted(_SEED_DIR.iterdir()):
            if not entry.is_dir():
                continue
            target = self._dir / entry.name
            if not target.exists():
                shutil.copytree(entry, target)
                logger.info("seeded agent: %s", entry.name)
                continue
            for seed_file in entry.iterdir():
                if seed_file.is_dir():
                    continue
                user_file = target / seed_file.name
                if not user_file.exists():
                    shutil.copy2(seed_file, user_file)
                    logger.info(
                        "seeded missing file %s for agent %s (partial cleanup recovery)",
                        seed_file.name, entry.name,
                    )

    def load_all(self) -> dict[str, Agent]:
        self._configs.clear()
        if not self._dir.exists():
            logger.warning("agents 目录 %s 不存在 — 未加载任何 agent", self._dir)
            return self._configs

        for entry in sorted(self._dir.iterdir()):
            if not entry.is_dir():
                continue
            yaml_path = entry / "agent.yaml"
            if not yaml_path.exists():
                continue
            try:
                raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    continue
                name = raw.get("name") or entry.name
                prompt = ""
                prompt_file = raw.get("prompt_file", "prompt.md")
                prompt_path = entry / prompt_file
                if prompt_path.exists():
                    prompt = prompt_path.read_text(encoding="utf-8")
                self._configs[name] = Agent(
                    name=name,
                    description=raw.get("description", ""),
                    prompt=prompt,
                    tools=raw.get("tools", []),
                    skills=raw.get("skills", []),
                    sub_agents=raw.get("sub_agents", []),
                    is_builtin=raw.get("is_builtin", False),
                    avatar=raw.get("avatar", ""),
                )
                logger.info(
                    "loaded agent: %s (tools=%s)", name, self._configs[name].tools,
                )
            except Exception:
                logger.exception("failed to load agent from %s", entry)

        return self._configs

    def get(self, name: str) -> Agent | None:
        return self._configs.get(name) or self._configs.get(name.lower())

    def all_names(self) -> list[str]:
        return list(self._configs.keys())

    def _agent_dir(self, name: str) -> Path:
        for entry in self._dir.iterdir():
            if not entry.is_dir():
                continue
            yaml_path = entry / "agent.yaml"
            if not yaml_path.exists():
                continue
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and (raw.get("name") or entry.name).lower() == name.lower():
                return entry
            if entry.name.lower() == name.lower():
                return entry
        return self._dir / name

    def _update_yaml(self, name: str, field: str, value: Any) -> None:
        d = self._agent_dir(name)
        yaml_path = d / "agent.yaml"
        if not yaml_path.exists():
            return
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return
        raw[field] = value
        yaml_path.write_text(
            yaml.dump(raw, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        cfg = self._configs.get(name)
        if cfg is not None:
            setattr(cfg, field, value)

    def save_prompt(self, name: str, prompt: str) -> None:
        d = self._agent_dir(name)
        yaml_path = d / "agent.yaml"
        prompt_file = "prompt.md"
        if yaml_path.exists():
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("prompt_file"):
                prompt_file = raw["prompt_file"]
        (d / prompt_file).write_text(prompt, encoding="utf-8")
        cfg = self._configs.get(name)
        if cfg is not None:
            cfg.prompt = prompt

    def save_tools(self, name: str, tools: list[str]) -> None:
        self._update_yaml(name, "tools", tools)

    def save_skills(self, name: str, skills: list[str]) -> None:
        self._update_yaml(name, "skills", skills)

    def save_description(self, name: str, description: str) -> None:
        self._update_yaml(name, "description", description)

    def save_avatar(self, name: str, preset_id: str) -> str:
        d = self._agent_dir(name)
        if not d.exists():
            raise AgentError(f"agent directory not found: {d}")

        preset_id = avatar.validate_preset_id(preset_id)
        svg_path = avatar.AVATARS_SEED_DIR / f"{preset_id}.svg"
        if not svg_path.exists():
            raise AgentError(f"avatar preset file not found: {svg_path}")
        svg_content = svg_path.read_text(encoding="utf-8")

        avatar_path = d / "avatar.svg"
        avatar_path.write_text(svg_content, encoding="utf-8")

        seed_dir = _SEED_DIR / name
        if seed_dir.exists():
            (seed_dir / "avatar.svg").write_text(svg_content, encoding="utf-8")

        self._update_yaml(name, "avatar", preset_id)

        logger.info("saved avatar for agent %s (preset=%s)", name, preset_id)
        return preset_id

    def create(
        self, name: str, prompt: str, tools: list[str], description: str = ""
    ) -> Agent:
        name = name.strip()
        if not name:
            raise AgentError("agent name cannot be empty")
        if name in self._configs:
            raise AgentError(f"agent '{name}' already exists")
        d = self._dir / name
        if d.exists():
            raise AgentError(f"directory '{d}' already exists")
        d.mkdir(parents=True, exist_ok=True)
        (d / "prompt.md").write_text(prompt or "", encoding="utf-8")
        yaml_data = {
            "name": name,
            "description": description,
            "prompt_file": "prompt.md",
            "tools": tools,
            "skills": [],
            "sub_agents": [],
            "is_builtin": False,
        }
        (d / "agent.yaml").write_text(
            yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        self._configs[name] = Agent(
            name=name,
            description=description,
            prompt=prompt or "",
            tools=tools,
        )
        logger.info("created agent: %s", name)
        return self._configs[name]

    def delete(self, name: str) -> None:
        cfg = self._configs.get(name)
        if not cfg:
            raise AgentError(f"agent '{name}' not found")
        if cfg.is_builtin:
            raise AgentError(f"cannot delete built-in agent '{name}'")
        d = self._agent_dir(name)
        if d.exists():
            shutil.rmtree(d)
        self._configs.pop(name, None)
        logger.info("deleted agent: %s", name)

    @property
    def configs(self) -> dict[str, Agent]:
        return self._configs

agent_loader = AgentLoader()
