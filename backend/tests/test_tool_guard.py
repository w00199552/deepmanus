from __future__ import annotations

import pytest
from langchain_core.messages import ToolMessage

from openmanus.middleware.tool_guard import ToolGuardMiddleware

class FakeModelRequest:

    def __init__(self, tools):
        self.tools = tools
        self.overridden_with = None

    def override(self, **kw):
        self.overridden_with = kw
        new = FakeModelRequest(kw.get("tools", self.tools))
        return new

class FakeToolCallRequest:

    def __init__(self, name: str, call_id: str = "tc1"):
        self.tool_call = {"name": name, "id": call_id}

def _fake_tool(name: str):
    class _T:
        pass
    t = _T()
    t.name = name
    return t

def _dict_tool(name: str) -> dict:
    return {"name": name, "description": f"fake {name}"}

@pytest.fixture
def guard_with_excludes():
    return ToolGuardMiddleware(
        excluded=frozenset({"write_file", "edit_file", "execute", "task", "write_todos"})
    )

@pytest.fixture
def guard_empty():
    return ToolGuardMiddleware(excluded=frozenset())

class TestModelCallFiltering:

    def test_excluded_tools_are_stripped_from_request(self, guard_with_excludes):
        req = FakeModelRequest([_fake_tool("read_file"), _fake_tool("write_file"), _fake_tool("ls")])
        captured = []

        def handler(r):
            captured.append(r)
            return "ok"

        guard_with_excludes.wrap_model_call(req, handler)
        assert len(captured) == 1
        passed_tools = captured[0].tools
        passed_names = {t.name for t in passed_tools}
        assert passed_names == {"read_file", "ls"}
        assert "write_file" not in passed_names

    def test_dict_shaped_tools_are_also_filtered(self, guard_with_excludes):
        req = FakeModelRequest([_dict_tool("read_file"), _dict_tool("execute"), _dict_tool("grep")])
        captured = []
        guard_with_excludes.wrap_model_call(req, lambda r: captured.append(r))
        passed_names = {t["name"] for t in captured[0].tools}
        assert passed_names == {"read_file", "grep"}

    def test_no_exclusions_passes_all_tools(self, guard_empty):
        tools = [_fake_tool("read_file"), _fake_tool("write_file")]
        req = FakeModelRequest(tools)
        captured = []
        guard_empty.wrap_model_call(req, lambda r: captured.append(r))
        assert captured[0].tools == tools

    def test_handler_return_value_is_passed_through(self, guard_with_excludes):
        req = FakeModelRequest([_fake_tool("read_file")])
        result = guard_with_excludes.wrap_model_call(req, lambda r: "the-result")
        assert result == "the-result"

    def test_request_with_only_excluded_tools_becomes_empty(self, guard_with_excludes):
        req = FakeModelRequest([_fake_tool("write_file"), _fake_tool("execute")])
        captured = []
        guard_with_excludes.wrap_model_call(req, lambda r: captured.append(r))
        assert captured[0].tools == []

class TestModelCallFilteringAsync:

    async def test_async_strips_excluded_tools(self, guard_with_excludes):
        req = FakeModelRequest([_fake_tool("read_file"), _fake_tool("write_file")])
        captured = []

        async def handler(r):
            captured.append(r)
            return "ok"

        await guard_with_excludes.awrap_model_call(req, handler)
        passed_names = {t.name for t in captured[0].tools}
        assert passed_names == {"read_file"}

    async def test_async_no_exclusions_passthrough(self, guard_empty):
        req = FakeModelRequest([_fake_tool("read_file")])

        async def handler(r):
            return "passthrough"

        result = await guard_empty.awrap_model_call(req, handler)
        assert result == "passthrough"

class TestToolCallRejection:

    def test_excluded_tool_call_returns_toolmessage_not_handler(self, guard_with_excludes):
        req = FakeToolCallRequest("write_file")
        handler_called = []

        def handler(r):
            handler_called.append(r)
            return "should-not-reach"

        result = guard_with_excludes.wrap_tool_call(req, handler)
        assert isinstance(result, ToolMessage)
        assert handler_called == [], "handler must NOT be invoked for excluded tools"
        assert "write_file" in result.content
        assert "not available" in result.content.lower()

    def test_allowed_tool_call_invokes_handler(self, guard_with_excludes):
        req = FakeToolCallRequest("read_file")
        handler_called = []

        def handler(r):
            handler_called.append(r)
            return "ran-read-file"

        result = guard_with_excludes.wrap_tool_call(req, handler)
        assert result == "ran-read-file"
        assert len(handler_called) == 1

    def test_rejected_message_carries_correct_tool_call_id(self, guard_with_excludes):
        req = FakeToolCallRequest("execute", call_id="call-xyz-123")
        result = guard_with_excludes.wrap_tool_call(req, lambda r: None)
        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "call-xyz-123"

    def test_rejected_message_name_is_the_blocked_tool(self, guard_with_excludes):
        req = FakeToolCallRequest("edit_file")
        result = guard_with_excludes.wrap_tool_call(req, lambda r: None)
        assert result.name == "edit_file"

    def test_empty_excluded_set_lets_everything_through(self, guard_empty):
        req = FakeToolCallRequest("write_file")
        result = guard_empty.wrap_tool_call(req, lambda r: "executed")
        assert result == "executed"

class TestToolCallRejectionAsync:
    async def test_async_rejects_excluded_tool(self, guard_with_excludes):
        req = FakeToolCallRequest("write_file")
        handler_called = []

        async def handler(r):
            handler_called.append(r)
            return "should-not-reach"

        result = await guard_with_excludes.awrap_tool_call(req, handler)
        assert isinstance(result, ToolMessage)
        assert handler_called == []

    async def test_async_allows_approved_tool(self, guard_with_excludes):
        req = FakeToolCallRequest("read_file")

        async def handler(r):
            return "ran"

        result = await guard_with_excludes.awrap_tool_call(req, handler)
        assert result == "ran"

class TestLayeredDefense:

    def test_researcher_cannot_write_even_if_request_leaked_it(self):
        guard = ToolGuardMiddleware(
            excluded=frozenset({"write_file", "edit_file", "execute"})
        )
        req = FakeToolCallRequest("write_file")
        result = guard.wrap_tool_call(req, lambda r: "wrote!")
        assert isinstance(result, ToolMessage)
        assert "wrote!" != result

    def test_manus_router_pattern_blocks_all_file_tools(self):
        from openmanus.agents.agent_factory import BUILTIN_TOOLS
        guard = ToolGuardMiddleware(excluded=BUILTIN_TOOLS)

        req = FakeModelRequest([_fake_tool(n) for n in ["read_file", "write_file", "execute"]])
        captured = []
        guard.wrap_model_call(req, lambda r: captured.append(r))
        assert captured[0].tools == []

        for forbidden in ["read_file", "write_file", "execute"]:
            r = guard.wrap_tool_call(FakeToolCallRequest(forbidden), lambda r: None)
            assert isinstance(r, ToolMessage), f"{forbidden} should be blocked"
