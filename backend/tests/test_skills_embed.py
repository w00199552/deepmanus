from __future__ import annotations

import os
import pytest
import sys
from pathlib import Path

from openmanus.skills import embed


@pytest.fixture
def embed_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "embed_python"
    d.mkdir()
    monkeypatch.setattr(embed, "EMBED_PYTHON_DIR", d)
    return d

class TestFindEmbedPython:
    def test_returns_none_when_dir_empty(self, embed_dir: Path):
        assert embed.find_embed_python() is None

    def test_returns_none_when_only_unrelated_files(self, embed_dir: Path):
        (embed_dir / "README.txt").write_text("not an interpreter", encoding="utf-8")
        assert embed.find_embed_python() is None

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="posix interpreter name (python3/python)",
    )
    def test_finds_python3_on_posix(self, embed_dir: Path):
        interp = embed_dir / "python3"
        interp.write_text("#!/bin/sh\n", encoding="utf-8")
        assert embed.find_embed_python() == interp

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="posix interpreter name (python3/python)",
    )
    def test_prefers_python3_then_python_on_posix(self, embed_dir: Path):
        py3 = embed_dir / "python3"
        py = embed_dir / "python"
        py3.write_text("#!/bin/sh\n", encoding="utf-8")
        py.write_text("#!/bin/sh\n", encoding="utf-8")
        assert embed.find_embed_python() == py3

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="windows interpreter name (python.exe)",
    )
    def test_finds_python_exe_on_windows(self, embed_dir: Path):
        interp = embed_dir / "python.exe"
        interp.write_bytes(b"MZ\x90\x00")
        assert embed.find_embed_python() == interp

class TestBuildSkillEnv:
    def test_returns_none_when_no_interpreter(self, embed_dir: Path, monkeypatch):
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        assert embed.build_skill_env() is None

    @pytest.mark.skipif(sys.platform == "win32", reason="posix PATH separator")
    def test_prepends_embed_dir_to_path_posix(self, embed_dir: Path, monkeypatch):
        (embed_dir / "python3").write_text("#!/bin/sh\n", encoding="utf-8")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        env = embed.build_skill_env()
        assert env is not None
        assert "PATH" in env
        first = env["PATH"].split(os.pathsep)[0]
        assert first == str(embed_dir)
        assert env["PATH"].endswith(":/usr/bin:/bin") or "/usr/bin:/bin" in env["PATH"]

    @pytest.mark.skipif(sys.platform != "win32", reason="windows PATH separator")
    def test_prepends_embed_dir_to_path_windows(self, embed_dir: Path, monkeypatch):
        (embed_dir / "python.exe").write_bytes(b"MZ\x90\x00")
        monkeypatch.setenv("PATH", r"C:\Windows\System32;C:\Windows")
        env = embed.build_skill_env()
        assert env is not None
        first = env["PATH"].split(os.pathsep)[0]
        assert first == str(embed_dir)

    def test_does_not_set_pythonhome_or_pythonpath(
        self, embed_dir: Path, monkeypatch
    ):
        if sys.platform == "win32":
            (embed_dir / "python.exe").write_bytes(b"MZ\x90\x00")
        else:
            (embed_dir / "python3").write_text("#!/bin/sh\n", encoding="utf-8")
        monkeypatch.setenv("PATH", "/usr/bin")
        env = embed.build_skill_env()
        assert env is not None
        assert "PYTHONHOME" not in env
        assert "PYTHONPATH" not in env
        assert set(env.keys()) == {"PATH"}

    def test_preserves_windows_critical_inherited_keys(
        self, embed_dir: Path, monkeypatch
    ):
        if sys.platform == "win32":
            (embed_dir / "python.exe").write_bytes(b"MZ\x90\x00")
        else:
            (embed_dir / "python3").write_text("#!/bin/sh\n", encoding="utf-8")
        monkeypatch.setenv("PATH", "/usr/bin")
        env = embed.build_skill_env()
        assert env is not None
        for key in ("SystemRoot", "COMSPEC", "WINDIR"):
            assert key not in env

    def test_idempotent_when_embed_already_first(
        self, embed_dir: Path, monkeypatch
    ):
        if sys.platform == "win32":
            (embed_dir / "python.exe").write_bytes(b"MZ\x90\x00")
        else:
            (embed_dir / "python3").write_text("#!/bin/sh\n", encoding="utf-8")
        monkeypatch.setenv("PATH", f"{embed_dir}{os.pathsep}/usr/bin")
        assert embed.build_skill_env() is None

class TestEnvOverride:
    def test_env_var_takes_precedence(self, tmp_path: Path, monkeypatch):
        custom = tmp_path / "custom_python"
        custom.mkdir()
        monkeypatch.setenv("OPENMANUS_PYTHON_HOME", str(custom))
        import importlib

        rt = importlib.reload(embed)
        try:
            assert rt.EMBED_PYTHON_DIR == custom
        finally:
            monkeypatch.delenv("OPENMANUS_PYTHON_HOME", raising=False)
            importlib.reload(embed)
