from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

def _load_module(workdir: Path):
    bfs = workdir / "bfs.py"
    if not bfs.exists():
        raise AssertionError("bfs.py was not created")
    sys.path.insert(0, str(workdir))
    try:
        spec = importlib.util.spec_from_file_location("bfs_under_test", bfs)
        if spec is None or spec.loader is None:
            raise AssertionError("could not load bfs.py as a module")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)

def check(workdir: Path) -> dict:
    mod = _load_module(workdir)
    if not hasattr(mod, "bfs"):
        raise AssertionError("bfs.py has no `bfs` function")

    g1 = {"A": ["B", "C"], "B": ["D"], "C": [], "D": []}
    got = mod.bfs(g1, "A")
    assert got == ["A", "B", "C", "D"], f"case1: expected [A,B,C,D], got {got}"

    assert mod.bfs({"X": []}, "X") == ["X"], "case2: single node failed"

    g3 = {"A": ["B"], "B": [], "C": ["D"], "D": []}
    got3 = mod.bfs(g3, "A")
    assert set(got3) == {"A", "B"}, f"case3: expected {{A,B}}, got {got3}"
    assert got3[0] == "A", "case3: BFS should start from the start node"

    g4 = {"A": ["B"], "B": ["C"], "C": ["A"]}
    got4 = mod.bfs(g4, "A")
    assert set(got4) == {"A", "B", "C"}, f"case4: cycle not handled, got {got4}"
    assert len(got4) == 3, "case4: revisited nodes in a cycle"

    return {"score": 1.0, "reason": "bfs correct on 4 cases (tree, single, disconnected, cycle)"}
