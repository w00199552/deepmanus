from __future__ import annotations

import argparse
import asyncio
import os
import re
import subprocess
import sys
import time
from conftest_eval import (
    _REPORTS_ROOT,
    AgentRunResult,
    list_tasks,
    load_task,
    prepare_workdir,
    run_coder,
)
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

COMMENT_DENSITY_THRESHOLD = 0.30
DIFF_BLOWUP_FACTOR = 2.0
NEVER_COMMIT_PENALTY = 0.40
NO_LINT_PENALTY = 0.05
REFORMAT_PENALTY = 0.15

@dataclass
class TaskResult:
    task_name: str
    completion_score: float = 0.0
    completion_reason: str = ""
    constraint_score: float = 1.0
    constraint_notes: list[str] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)
    agent_error: str | None = None
    duration_s: float = 0.0
    workdir: str = ""

async def evaluate_task(task_name: str) -> TaskResult:
    result = TaskResult(task_name=task_name)
    prompt, check_fn = load_task(task_name)

    workdir = prepare_workdir(task_name)
    result.workdir = str(workdir)

    start = time.time()
    print(f"\n▶ {task_name}: running Coder in {workdir} ...", flush=True)
    run: AgentRunResult = await run_coder(prompt, str(workdir))
    result.duration_s = round(time.time() - start, 1)
    result.tools_called = [t.name for t in run.tool_calls]
    result.agent_error = run.error

    if run.error:
        result.completion_reason = f"agent error: {run.error}"
        result.constraint_notes.append(f"agent errored out: {run.error}")
        result.constraint_score = 0.0
        return result

    try:
        outcome = check_fn(Path(workdir))
        result.completion_score = float(outcome.get("score", 0.0))
        result.completion_reason = outcome.get("reason", "")
    except AssertionError as e:
        result.completion_score = 0.0
        result.completion_reason = f"check failed: {e}"
    except Exception as e:
        result.completion_score = 0.0
        result.completion_reason = f"check crashed: {type(e).__name__}: {e}"

    score_constraints(result, run, Path(workdir), task_name)

    return result

def score_constraints(
    result: TaskResult, run: AgentRunResult, workdir: Path, task_name: str
) -> None:
    notes: list[str] = []
    deductions: list[float] = []

    commit_run = any(
        t.name == "execute" and re.search(r"\bgit\s+commit\b", t.args)
        for t in run.tool_calls
    )
    if commit_run:
        notes.append("⚠️ ran `git commit` (violates NEVER commit)")
        deductions.append(NEVER_COMMIT_PENALTY)
    else:
        notes.append("didn't run `git commit` (respects NEVER commit)")

    comment_ratio = _comment_density(workdir, task_name)
    if comment_ratio is not None:
        if comment_ratio > COMMENT_DENSITY_THRESHOLD:
            notes.append(f"⚠️ comment density {comment_ratio:.0%} (>{COMMENT_DENSITY_THRESHOLD:.0%})")
            deductions.append(min(0.15, (comment_ratio - COMMENT_DENSITY_THRESHOLD) * 0.3))
        else:
            notes.append(f"comment density {comment_ratio:.0%} (OK)")

    unrelated = _unrelated_changes(workdir, task_name)
    if unrelated:
        notes.append(f"⚠️ touched unrelated files: {', '.join(unrelated)}")
        deductions.append(REFORMAT_PENALTY * len(unrelated))

    has_lint_config = _has_lint_config(workdir)
    if has_lint_config:
        ran_lint = any(
            t.name == "execute" and re.search(r"\b(lint|typecheck|ruff|eslint|mypy|tsc)\b", t.args)
            for t in run.tool_calls
        )
        if ran_lint:
            notes.append("ran a lint/typecheck command (good)")
        else:
            notes.append("(didn't run lint/typecheck — mild)")
            deductions.append(NO_LINT_PENALTY)
    else:
        notes.append("no lint config in project — lint check skipped")

    result.constraint_notes = notes
    result.constraint_score = max(0.0, 1.0 - sum(deductions))

def _comment_density(workdir: Path, task_name: str) -> float | None:
    py_files = list(workdir.rglob("*.py"))
    py_files = [p for p in py_files if not p.name.startswith("test_") or p.name == "test_search.py"]
    py_files = [p for p in py_files if p.name != "test_search.py"]
    if not py_files:
        return None
    total = 0
    comments = 0
    for p in py_files:
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            total += 1
            if stripped.startswith("#"):
                comments += 1
    if total == 0:
        return None
    return comments / total

def _unrelated_changes(workdir: Path, task_name: str) -> list[str]:
    expected: dict[str, set[str]] = {
        "bfs": {"bfs.py"},
        "add_param": {"calc.py"},
        "fix_bug": {"search.py"},
    }
    allowed = expected.get(task_name)
    if allowed is None:
        return []
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(workdir), capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return []
        out2 = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(workdir), capture_output=True, text=True, timeout=5,
        )
        changed = set(out.stdout.split()) | set(out2.stdout.split())
        changed = {f for f in changed if not _is_test_file(f)}
        return sorted(changed - allowed)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

def _is_test_file(path: str) -> bool:
    import os
    name = os.path.basename(path).lower()
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_test.go")
        or name.endswith(".test.js")
        or name.endswith(".test.ts")
        or name.endswith(".spec.js")
        or name.endswith(".spec.ts")
    )

_LINT_CONFIG_FILES = {
    "pyproject.toml", "ruff.toml", ".ruff.toml", "setup.cfg",
    ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml",
    "eslint.config.js", "eslint.config.mjs",
    "tsconfig.json",
    ".golangci.yml", ".golangci.yaml",
}

def _has_lint_config(workdir: Path) -> bool:
    return any((workdir / name).exists() for name in _LINT_CONFIG_FILES)

def write_report(results: list[TaskResult], argv: list[str]) -> Path:
    _REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = _REPORTS_ROOT / f"{ts}.md"

    def pct(x: float) -> str:
        return f"{x:.0%}"

    lines = [
        "# Coder Eval Report",
        "",
        f"- **Timestamp**: {datetime.now().isoformat(timespec='seconds')}",
        f"- **Tasks**: {len(results)}",
        f"- **Command**: `{' '.join(argv)}`",
        f"- **Model**: from `backend/.env` (resolved at runtime)",
        "",
        "## Per-task results",
        "",
    ]

    for i, r in enumerate(results, 1):
        emoji = "✅" if r.completion_score >= 1.0 else ("⚠️" if r.completion_score > 0 else "❌")
        lines.append(f"### {i}. {r.task_name} {emoji}")
        lines.append("")
        lines.append(f"- **Completion**: {pct(r.completion_score)} — {r.completion_reason}")
        lines.append(f"- **Constraints**: {pct(r.constraint_score)}")
        for note in r.constraint_notes:
            lines.append(f"  - {note}")
        if r.agent_error:
            lines.append(f"- **Agent error**: {r.agent_error}")
        lines.append(f"- **Tools called**: {', '.join(r.tools_called) or '(none)'}")
        lines.append(f"- **Duration**: {r.duration_s}s")
        lines.append(f"- **Workdir** (kept for inspection): `{r.workdir}`")
        lines.append("")

    if results:
        avg_c = sum(r.completion_score for r in results) / len(results)
        avg_k = sum(r.constraint_score for r in results) / len(results)
        total_t = sum(r.duration_s for r in results)
        lines += [
            "## Summary",
            "",
            f"- Avg completion: **{pct(avg_c)}**",
            f"- Avg constraints: **{pct(avg_k)}**",
            f"- Total duration: {total_t:.0f}s",
            "",
            "> Single-run results are samples. Re-run the same task a few times",
            "> and average to smooth out LLM variance.",
            "",
        ]

    report.write_text("\n".join(lines), encoding="utf-8")
    return report

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Coder behavior eval.")
    parser.add_argument("tasks", nargs="*", help="task names to run (default: all)")
    parser.add_argument("--list", action="store_true", help="list available tasks and exit")
    args = parser.parse_args(argv[1:])

    if args.list:
        print("Available tasks:")
        for t in list_tasks():
            print(f"  {t}")
        return 0

    tasks = args.tasks or list_tasks()
    unknown = [t for t in tasks if t not in set(list_tasks())]
    if unknown:
        print(f"Unknown task(s): {unknown}", file=sys.stderr)
        print(f"Available: {list_tasks()}", file=sys.stderr)
        return 2

    print(f"Running eval on {len(tasks)} task(s): {', '.join(tasks)}")
    results = asyncio.run(_run_all(tasks))

    report = write_report(results, argv)
    print(f"\n=== Report written to {report} ===\n")
    print(report.read_text(encoding="utf-8"))
    return 0

async def _run_all(tasks: list[str]) -> list[TaskResult]:
    results = []
    for t in tasks:
        try:
            r = await evaluate_task(t)
        except Exception as e:
            r = TaskResult(task_name=t, agent_error=f"{type(e).__name__}: {e}")
        results.append(r)
        _print_inline(r)
    return results

def _print_inline(r: TaskResult) -> None:
    status = "✅" if r.completion_score >= 1.0 else "❌"
    print(
        f"  {status} {r.task_name}: completion={r.completion_score:.0%} "
        f"constraints={r.constraint_score:.0%} ({r.duration_s}s, "
        f"{len(r.tools_called)} tool calls)",
        flush=True,
    )

if __name__ == "__main__":
    sys.exit(main(sys.argv))
