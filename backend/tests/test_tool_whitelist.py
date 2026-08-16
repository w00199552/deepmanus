from __future__ import annotations

import pytest

from openmanus.agents.agent_factory import BUILTIN_TOOLS, resolve_tool_whitelist

SEED_TOOLS = {
    "Manus": ["dispatch"],
    "Coder": ["read_file", "write_file", "edit_file", "ls", "glob", "grep", "execute"],
    "Researcher": ["read_file", "ls", "glob", "grep"],
    "TeamLeader": [
        "dispatch", "send_message", "read_mailbox",
        "whiteboard_write", "whiteboard_read",
    ],
}

WRITE_EXEC_TOOLS = ["write_file", "edit_file", "execute", "task", "write_todos"]

class TestSeedAgentBoundaries:

    @pytest.mark.parametrize("agent_name", list(SEED_TOOLS))
    def test_partition_is_exhaustive_and_disjoint(self, agent_name):
        kept, excluded, _ = resolve_tool_whitelist(SEED_TOOLS[agent_name])
        assert kept | excluded == BUILTIN_TOOLS
        assert kept & excluded == frozenset()

    def test_researcher_is_read_only(self):
        kept, excluded, _ = resolve_tool_whitelist(SEED_TOOLS["Researcher"])
        for forbidden in WRITE_EXEC_TOOLS:
            assert forbidden in excluded, (
                f"Researcher should exclude {forbidden}; excluded={sorted(excluded)}"
            )
        for required in ("read_file", "ls", "glob", "grep"):
            assert required in kept

    def test_coder_has_write_execute_but_no_task(self):
        kept, excluded, _ = resolve_tool_whitelist(SEED_TOOLS["Coder"])
        for required in ("read_file", "write_file", "edit_file", "execute", "ls", "glob", "grep"):
            assert required in kept
        assert "task" in excluded
        assert "write_todos" in excluded

    def test_manus_keeps_no_builtins(self):
        kept, excluded, extras = resolve_tool_whitelist(SEED_TOOLS["Manus"])
        assert kept == frozenset()
        assert excluded == BUILTIN_TOOLS
        assert extras == ["dispatch"]

    def test_teamleader_keeps_no_builtins(self):
        kept, excluded, extras = resolve_tool_whitelist(SEED_TOOLS["TeamLeader"])
        assert kept == frozenset()
        assert excluded == BUILTIN_TOOLS
        assert extras == sorted(SEED_TOOLS["TeamLeader"])

class TestWhitelistEdgeCases:

    def test_empty_whitelist_excludes_every_builtin(self):
        kept, excluded, extras = resolve_tool_whitelist([])
        assert kept == frozenset()
        assert excluded == BUILTIN_TOOLS
        assert extras == []

    def test_all_builtins_whitelisted_excludes_none(self):
        all_builtins = list(BUILTIN_TOOLS)
        kept, excluded, extras = resolve_tool_whitelist(all_builtins)
        assert kept == BUILTIN_TOOLS
        assert excluded == frozenset()
        assert extras == []

    def test_only_extras_no_builtins(self):
        kept, excluded, extras = resolve_tool_whitelist(["dispatch", "send_message"])
        assert kept == frozenset()
        assert excluded == BUILTIN_TOOLS
        assert extras == ["dispatch", "send_message"]

    def test_mixed_builtins_and_extras(self):
        kept, excluded, extras = resolve_tool_whitelist(
            ["read_file", "execute", "dispatch", "whiteboard_read"]
        )
        assert kept == frozenset({"read_file", "execute"})
        assert excluded == (BUILTIN_TOOLS - {"read_file", "execute"})
        assert extras == ["dispatch", "whiteboard_read"]

    def test_unknown_builtin_silently_treated_as_extra(self):
        kept, excluded, extras = resolve_tool_whitelist(["read_file", "readfile_typo"])
        assert kept == frozenset({"read_file"})
        assert "readfile_typo" in extras

    def test_accepts_set_input(self):
        kept_list, _, _ = resolve_tool_whitelist(["read_file", "execute"])
        kept_set, _, _ = resolve_tool_whitelist({"read_file", "execute"})
        assert kept_list == kept_set

    def test_duplicates_collapse(self):
        kept, excluded, _ = resolve_tool_whitelist(["read_file", "read_file", "read_file"])
        assert kept == frozenset({"read_file"})
        assert excluded == BUILTIN_TOOLS - {"read_file"}

    def test_returns_frozensets_for_immutability(self):
        kept, excluded, _ = resolve_tool_whitelist(["read_file"])
        assert isinstance(kept, frozenset)
        assert isinstance(excluded, frozenset)

    def test_extras_returned_sorted(self):
        _, _, extras = resolve_tool_whitelist(["zebra_tool", "alpha_tool", "read_file"])
        assert extras == sorted(["zebra_tool", "alpha_tool"])
