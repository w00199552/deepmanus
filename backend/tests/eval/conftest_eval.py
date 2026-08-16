from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_EVAL_ROOT = Path(__file__).resolve().parent
_FIXTURES_ROOT = _EVAL_ROOT / "fixtures"
_REPORTS_ROOT = _EVAL_ROOT / "reports"
_BACKEND_ROOT = _EVAL_ROOT.parent.parent

_DB_TEMPDIR = tempfile.mkdtemp(prefix="openmanus_eval_db_")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(_DB_TEMPDIR) / 'checkpoints.db'}")

from openmanus.agents.agent_factory import build_agent, close_agent
from openmanus.db import init_db, session_store
from langchain_core.messages import HumanMessage

logger = logging.getLogger("openmanus.eval")

def prepare_workdir(task_name: str) -> Path:
    fixture = _FIXTURES_ROOT / task_name
    if not fixture.exists():
        raise FileNotFoundError(f"no fixture named {task_name!r} at {fixture}")

    workdir = Path(tempfile.mkdtemp(prefix=f"openmanus_eval_{task_name}_"))

    starter = fixture / "starter"
    if starter.exists():
        shutil.copytree(starter, workdir, dirs_exist_ok=True)

    (workdir / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")

    try:
        subprocess.run(
            ["git", "init", "-q"], cwd=str(workdir),
            check=True, capture_output=True, timeout=5,
        )
        subprocess.run(
            ["git", "add", "-A"], cwd=str(workdir),
            check=True, capture_output=True, timeout=5,
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "fixture baseline"],
            cwd=str(workdir),
            env={**os.environ,
                 "GIT_AUTHOR_NAME": "eval", "GIT_AUTHOR_EMAIL": "eval@local",
                 "GIT_COMMITTER_NAME": "eval", "GIT_COMMITTER_EMAIL": "eval@local"},
            check=True, capture_output=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        logger.warning("git not available in %s — diff-based scoring will be skipped", workdir)

    return workdir

@dataclass
class ToolCallRecord:
    name: str
    args: str
    result_preview: str = ""

@dataclass
class AgentRunResult:
    final_text: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    error: str | None = None
    message_count: int = 0

async def _ensure_db() -> None:
    from openmanus.agents.loader import agent_loader
    if not agent_loader.configs:
        agent_loader.load_all()
        logger.info("eval: loaded %d agents from %s", len(agent_loader.configs), agent_loader.dir)
    from openmanus.tool_loader import tool_loader
    tool_loader.load_all()
    from openmanus.skill_loader import skill_loader
    skill_loader.load_all()
    await init_db()

async def run_coder(task_prompt: str, workdir: str, *, max_turns: int = 40) -> AgentRunResult:
    await _ensure_db()

    session = await session_store.create(
        kind="subagent", name="Coder",
        title=f"eval: {Path(workdir).name}",
        workdir=workdir,
    )
    session_id = session["id"]

    result = AgentRunResult()
    agent = await build_agent(session_id)
    config = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": max_turns * 6,
    }

    pending: dict[str, ToolCallRecord] = {}

    try:
        async for chunk in agent.astream(
            {"messages": [HumanMessage(content=task_prompt)]},
            config=config,
            stream_mode=["messages", "updates"],
            subgraphs=False,
            version="v2",
        ):
            _absorb_chunk(chunk, result, pending)
        result.final_text = await _extract_final_text(agent, config)
    except Exception as exc:
        logger.exception("agent stream failed for session %s", session_id)
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        await close_agent(agent)

    return result

def _absorb_chunk(chunk, result: AgentRunResult, pending: dict) -> None:
    if not isinstance(chunk, dict):
        return
    kind = chunk.get("type")
    data = chunk.get("data")
    if kind == "messages":
        msg = data[0] if isinstance(data, tuple) and data else None
        if msg is None:
            return
        _handle_message(msg, result, pending)
    elif kind == "updates":
        if isinstance(data, dict):
            for node_state in data.values():
                msgs = (node_state or {}).get("messages") if isinstance(node_state, dict) else None
                if isinstance(msgs, list):
                    result.message_count += len(msgs)

def _handle_message(msg, result: AgentRunResult, pending: dict) -> None:
    tcc = getattr(msg, "tool_call_chunks", None) or []
    for c in tcc:
        if not isinstance(c, dict):
            continue
        name = c.get("name") or ""
        cid = c.get("id") or ""
        args = c.get("args")
        if cid and cid not in pending:
            rec = ToolCallRecord(name=name or "(streaming)", args="")
            pending[cid] = rec
            result.tool_calls.append(rec)
        if cid and cid in pending:
            rec = pending[cid]
            if name and (rec.name == "(streaming)" or not rec.name):
                rec.name = name
            if args:
                rec.args += str(args)
    if type(msg).__name__ == "ToolMessage":
        tcid = getattr(msg, "tool_call_id", None)
        content = getattr(msg, "content", "")
        if tcid and tcid in pending:
            preview = str(content)[:120].replace("\n", " ")
            pending[tcid].result_preview = preview

async def _extract_final_text(agent, config) -> str:
    try:
        state = await agent.aget_state(config)
        messages = (state.values or {}).get("messages", [])
        for msg in reversed(messages):
            content = getattr(msg, "content", "")
            if getattr(msg, "type", "") == "ai" and content:
                if isinstance(content, list):
                    return " ".join(
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ).strip()
                return str(content).strip()
    except Exception:
        logger.debug("could not extract final text", exc_info=True)
    return ""

def load_task(task_name: str) -> tuple[str, Any]:
    fixture = _FIXTURES_ROOT / task_name
    task_file = fixture / "task.md"
    if not task_file.exists():
        raise FileNotFoundError(f"fixture {task_name!r} has no task.md")
    prompt = task_file.read_text(encoding="utf-8")

    check_path = fixture / "check.py"
    if not check_path.exists():
        raise FileNotFoundError(f"fixture {task_name!r} has no check.py")
    spec = importlib.util.spec_from_file_location(f"eval_check_{task_name}", check_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "check"):
        raise AttributeError(f"{check_path} has no `check` function")
    return prompt, mod.check

def list_tasks() -> list[str]:
    out = []
    for d in sorted(_FIXTURES_ROOT.iterdir()):
        if d.is_dir() and (d / "task.md").exists() and (d / "check.py").exists():
            out.append(d.name)
    return out
