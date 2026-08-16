from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

import yaml

from openmanus.log import logger

OPENMANUS_HOME = Path(os.environ.get("OPENMANUS_HOME", Path.home() / ".openmanus"))
TOOLS_DIR = OPENMANUS_HOME / "tools"

class ToolLoader:

    def __init__(self, tools_dir: Path | None = None) -> None:
        self._dir = tools_dir or TOOLS_DIR
        self._tools: dict[str, Any] = {}

    @property
    def dir(self) -> Path:
        return self._dir

    def load_all(self) -> dict[str, Any]:
        self._tools.clear()
        if not self._dir.exists():
            logger.info("tools 目录 %s 不存在 — 未加载用户工具", self._dir)
            return self._tools

        for entry in sorted(self._dir.iterdir()):
            if not entry.is_dir():
                continue
            yaml_path = entry / "tool.yaml"
            if not yaml_path.exists():
                continue
            try:
                self._load_one(entry, yaml_path)
            except Exception:
                logger.exception("failed to load tool from %s", entry)

        return self._tools

    def _load_one(self, tool_dir: Path, yaml_path: Path) -> None:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return

        name = raw.get("name") or tool_dir.name
        entry_file = raw.get("entry", "tool.py")
        class_name = raw.get("class", "")

        if not class_name:
            logger.warning("tool %s: tool.yaml 缺少 'class'，跳过", name)
            return

        if entry_file.endswith(".py"):
            entry_file = entry_file[:-3]
        py_path = tool_dir / f"{entry_file}.py"
        if not py_path.exists():
            logger.warning("tool %s: 入口文件 %s 不存在", name, py_path)
            return

        module_name = f"openmanus_user_tool.{name}"
        spec = importlib.util.spec_from_file_location(module_name, str(py_path))
        if spec is None or spec.loader is None:
            logger.warning("tool %s: 无法创建 module spec", name)
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        tool_class = getattr(mod, class_name, None)
        if tool_class is None:
            logger.warning("tool %s: 类 %s 不在 %s 中", name, class_name, py_path)
            return

        instance = tool_class()
        self._tools[name] = instance
        logger.info("loaded user tool: %s (class=%s from %s)", name, class_name, py_path.name)

    def get(self, name: str) -> Any | None:
        return self._tools.get(name)

    def all_names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def tools(self) -> dict[str, Any]:
        return self._tools

tool_loader = ToolLoader()
