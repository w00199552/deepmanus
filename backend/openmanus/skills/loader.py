from __future__ import annotations

import os
import re
import yaml
from pathlib import Path

from openmanus.log import logger
from openmanus.skills.entities import Skill

OPENMANUS_HOME = Path(os.environ.get("OPENMANUS_HOME", Path.home() / ".openmanus"))
SKILLS_DIR = OPENMANUS_HOME / "skills"

def _parse_frontmatter(content: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

class SkillLoader:

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._dir = skills_dir or SKILLS_DIR
        self._skills: dict[str, Skill] = {}

    @property
    def dir(self) -> Path:
        return self._dir

    def load_all(self) -> dict[str, Skill]:
        self._skills.clear()
        if not self._dir.exists():
            logger.info("skills 目录 %s 不存在 — 未加载任何 skill", self._dir)
            return self._skills

        for entry in sorted(self._dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
                fm = _parse_frontmatter(content)
                name = fm.get("name", entry.name)
                self._skills[name] = Skill(
                    name=name,
                    description=fm.get("description", ""),
                    dir=str(entry),
                    has_scripts=(entry / "scripts").is_dir(),
                    has_references=(entry / "references").is_dir(),
                )
                logger.info("loaded skill: %s", name)
            except Exception:
                logger.exception("failed to load skill from %s", entry)

        return self._skills

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all_names(self) -> list[str]:
        return list(self._skills.keys())

    def skill_dir(self, name: str) -> Path | None:
        s = self._skills.get(name)
        return Path(s.dir) if s else None

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills

skill_loader = SkillLoader()
