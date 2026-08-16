from __future__ import annotations

import pytest

from openmanus.tools.tool_loader import ToolLoader

_VALID_ENTRY_PY = '''\
"""A minimal valid user tool."""
from langchain_core.tools import BaseTool

class EchoTool(BaseTool):
    name: str = "echo"
    description: str = "Echoes the input back."

    def _run(self, text: str = "") -> str:
        return text

    async def _arun(self, text: str = "") -> str:
        return text
'''

def _make_tool_dir(
    root,
    name: str,
    *,
    entry_text: str = _VALID_ENTRY_PY,
    entry_filename: str = "entry.py",
    yaml_body: str | None = None,
    class_name: str = "EchoTool",
    description: str = "echoes input",
) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    if yaml_body is None:
        yaml_body = (
            f"name: {name}\n"
            f"entry: {entry_filename[:-3] if entry_filename.endswith('.py') else entry_filename}\n"
            f"class: {class_name}\n"
            f"description: {description}\n"
        )
    (d / "tool.yaml").write_text(yaml_body, encoding="utf-8")
    (d / entry_filename).write_text(entry_text, encoding="utf-8")

class TestLoadHappyPath:
    def test_loads_a_valid_tool(self, tmp_path):
        _make_tool_dir(tmp_path, "echo")
        loader = ToolLoader(tools_dir=tmp_path)
        loaded = loader.load_all()
        assert "echo" in loaded
        tool = loader.get("echo")
        assert tool is not None
        assert tool.name == "echo"
        assert "echo" in loader.all_names()

    def test_loads_multiple_tools(self, tmp_path):
        _make_tool_dir(tmp_path, "echo", class_name="EchoTool")
        _make_tool_dir(
            tmp_path, "counter",
            entry_text=(
                "from langchain_core.tools import BaseTool\n"
                "class CounterTool(BaseTool):\n"
                '    name: str = "counter"\n'
                '    description: str = "counts"\n'
                "    def _run(self, n: int = 0) -> int:\n"
                "        return n + 1\n"
                "    async def _arun(self, n: int = 0) -> int:\n"
                "        return n + 1\n"
            ),
            class_name="CounterTool",
        )
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert set(loader.all_names()) == {"echo", "counter"}

    def test_load_all_is_idempotent_reload(self, tmp_path):
        _make_tool_dir(tmp_path, "echo")
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        loader.load_all()
        assert loader.all_names() == ["echo"]

    def test_tool_is_callable(self, tmp_path):
        _make_tool_dir(tmp_path, "echo")
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        tool = loader.get("echo")
        assert tool.invoke({"text": "hello"}) == "hello"

    def test_entry_filename_with_py_suffix_is_accepted(self, tmp_path):
        _make_tool_dir(
            tmp_path, "echo",
            entry_filename="entry.py",
            yaml_body="name: echo\nentry: entry.py\nclass: EchoTool\ndescription: x\n",
        )
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert loader.get("echo") is not None

    def test_entry_filename_without_py_suffix_is_accepted(self, tmp_path):
        _make_tool_dir(
            tmp_path, "echo",
            entry_filename="entry.py",
            yaml_body="name: echo\nentry: entry\nclass: EchoTool\ndescription: x\n",
        )
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert loader.get("echo") is not None

class TestEmptyAndMissing:
    def test_missing_dir_returns_empty(self, tmp_path):
        loader = ToolLoader(tools_dir=tmp_path / "does_not_exist")
        loaded = loader.load_all()
        assert loaded == {}
        assert loader.all_names() == []

    def test_empty_dir_returns_empty(self, tmp_path):
        loader = ToolLoader(tools_dir=tmp_path)
        assert loader.load_all() == {}

    def test_files_in_dir_are_skipped(self, tmp_path):
        (tmp_path / "loose_file.txt").write_text("ignore me", encoding="utf-8")
        loader = ToolLoader(tools_dir=tmp_path)
        assert loader.load_all() == {}

class TestMalformedConfigs:

    def test_subdir_without_tool_yaml_is_skipped(self, tmp_path):
        (tmp_path / "orphan").mkdir()
        _make_tool_dir(tmp_path, "echo")
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert loader.all_names() == ["echo"]

    def test_missing_class_field_is_skipped(self, tmp_path):
        _make_tool_dir(
            tmp_path, "no_class",
            yaml_body="name: no_class\nentry: entry\ndescription: x\n",
        )
        _make_tool_dir(tmp_path, "echo")
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert loader.all_names() == ["echo"]

    def test_missing_entry_file_is_skipped(self, tmp_path):
        _make_tool_dir(
            tmp_path, "no_entry_file",
            entry_filename="entry.py",
            yaml_body="name: no_entry_file\nentry: missing\nclass: EchoTool\ndescription: x\n",
        )
        _make_tool_dir(tmp_path, "echo")
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert loader.all_names() == ["echo"]

    def test_class_not_found_in_entry_is_skipped(self, tmp_path):
        _make_tool_dir(
            tmp_path, "wrong_class",
            entry_text="pass\n",
            yaml_body="name: wrong_class\nentry: entry\nclass: EchoTool\ndescription: x\n",
        )
        _make_tool_dir(tmp_path, "echo")
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert loader.all_names() == ["echo"]

    def test_invalid_yaml_is_skipped(self, tmp_path):
        d = tmp_path / "bad_yaml"
        d.mkdir()
        (d / "tool.yaml").write_text("this: is: not: valid: yaml: [", encoding="utf-8")
        (d / "entry.py").write_text("pass", encoding="utf-8")
        _make_tool_dir(tmp_path, "echo")
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert loader.all_names() == ["echo"]

    def test_entry_module_with_import_error_is_skipped(self, tmp_path):
        _make_tool_dir(
            tmp_path, "bad_import",
            entry_text="import this_module_does_not_exist_anywhere\n",
            yaml_body="name: bad_import\nentry: entry\nclass: EchoTool\ndescription: x\n",
        )
        _make_tool_dir(tmp_path, "echo")
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert loader.all_names() == ["echo"]

class TestNameResolution:
    def test_name_falls_back_to_dir_name(self, tmp_path):
        _make_tool_dir(
            tmp_path, "my_tool",
            yaml_body="entry: entry\nclass: EchoTool\ndescription: x\n",
        )
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert "my_tool" in loader.all_names()

    def test_get_unknown_name_returns_none(self, tmp_path):
        loader = ToolLoader(tools_dir=tmp_path)
        loader.load_all()
        assert loader.get("nonexistent") is None

    def test_dir_property_returns_configured_path(self, tmp_path):
        loader = ToolLoader(tools_dir=tmp_path)
        assert loader.dir == tmp_path
