from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from openmanus.common.exceptions import NotFoundError, SandboxError, ValidationError
from openmanus.config import settings
from openmanus.log import logger
from openmanus.sandbox.entities import ChildrenResult, FileContent, FileNode, WriteResult

_HIDE = frozenset({"__pycache__", "node_modules", ".git"})

_CODE_EXTS = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx", ".sh", ".json", ".yaml", ".yml",
    ".css", ".html", ".xml", ".sql", ".toml", ".cfg", ".ini",
})
_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"})

def _skip(name: str) -> bool:
    return name.startswith(".") or name in _HIDE

def get_workdir(workdir: str | None = None) -> Path:
    base = workdir or settings.workdir
    return Path(base).resolve()

def safe_path(path: str, workdir: str | None = None) -> Path:
    wd = get_workdir(workdir)
    target = (wd / path).resolve()
    try:
        target.relative_to(wd)
    except ValueError:
        raise SandboxError("path outside workdir") from None
    return target

def _classify_file(ext: str) -> str:
    if ext == ".md":
        return "markdown"
    if ext in _CODE_EXTS:
        return "code"
    if ext in _IMAGE_EXTS:
        return "image"
    return "text"

def _build_node(path: Path, relative: str) -> FileNode:
    is_dir = path.is_dir()
    has_children = False
    if is_dir:
        try:
            has_children = any(not _skip(c.name) for c in path.iterdir())
        except (PermissionError, OSError):
            pass
    return FileNode(
        name=path.name or str(path),
        path=relative,
        type="dir" if is_dir else "file",
        size=path.stat().st_size if not is_dir else 0,
        children=[],
        has_children=has_children,
    )

def _list_children_nodes(path: Path, relative: str) -> list[FileNode]:
    out: list[FileNode] = []
    try:
        for child in sorted(path.iterdir(), key=lambda c: (not c.is_dir(), c.name)):
            if _skip(child.name):
                continue
            child_rel = f"{relative}/{child.name}" if relative else child.name
            out.append(_build_node(child, child_rel))
    except (PermissionError, OSError):
        pass
    return out

def get_tree(workdir: str | None = None) -> FileNode:
    wd = get_workdir(workdir)
    root = _build_node(wd, "")
    root.children = _list_children_nodes(wd, "")
    return root

def list_children(path: str, workdir: str | None = None) -> ChildrenResult:
    target = safe_path(path, workdir) if path else get_workdir(workdir)
    if not target.is_dir():
        raise ValidationError("not a directory")
    return ChildrenResult(path=path, children=_list_children_nodes(target, path))

def read_file(path: str, workdir: str | None = None) -> FileContent:
    target = safe_path(path, workdir)
    if not target.exists() or not target.is_file():
        raise NotFoundError(f"file not found: {path}")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return FileContent(path=path, name=target.name, content="(binary file)", file_type="binary")

    return FileContent(
        path=path,
        name=target.name,
        content=content,
        file_type=_classify_file(target.suffix.lower()),
    )

def write_file(path: str, content: str, workdir: str | None = None) -> WriteResult:
    target = safe_path(path, workdir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return WriteResult(ok=True, path=path)

def delete_path(path: str, workdir: str | None = None) -> WriteResult:
    import shutil

    target = safe_path(path, workdir)
    if not target.exists():
        raise NotFoundError(f"path does not exist: {path}")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return WriteResult(ok=True, path=path)

def make_dir(path: str, workdir: str | None = None) -> WriteResult:
    target = safe_path(path, workdir)
    target.mkdir(parents=True, exist_ok=True)
    return WriteResult(ok=True, path=path)

def create_file(path: str, workdir: str | None = None) -> WriteResult:
    target = safe_path(path, workdir)
    if target.exists():
        raise ValidationError(f"file already exists: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")
    return WriteResult(ok=True, path=path)

class FileWatcher:

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._observer = None
        self._watch = None
        self._wd_resolved: Path | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None

    def _ensure_observer(self) -> None:
        if self._observer is not None:
            return
        try:
            from watchdog.observers import Observer
        except ImportError:
            logger.warning("watchdog 未安装 — 文件监听已禁用")
            return
        self._observer = Observer()
        self._observer.daemon = True
        self._observer.start()
        logger.info("watchdog observer 已启动")

    def _make_handler(self):
        from watchdog.events import FileSystemEventHandler

        wd = self._wd_resolved
        hub = self

        class Handler(FileSystemEventHandler):
            def _push(self, event_type: str, src_path: str) -> None:
                if hub._queue is None or hub._loop is None or wd is None:
                    return
                try:
                    rel = str(Path(src_path).resolve().relative_to(wd)).replace("\\", "/")
                except (ValueError, OSError):
                    return
                if any(
                    part.startswith(".") or part == "__pycache__" or part == "node_modules"
                    for part in Path(rel).parts
                ):
                    return
                hub._loop.call_soon_threadsafe(
                    hub._queue.put_nowait, {"type": event_type, "path": rel},
                )

            def on_created(self, event):
                self._push("created", event.src_path)

            def on_modified(self, event):
                self._push("modified", event.src_path)

            def on_deleted(self, event):
                self._push("deleted", event.src_path)

            def on_moved(self, event):
                self._push("moved", event.src_path)

        return Handler()

    def start(self, wd_str: str, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
        wd_resolved = Path(wd_str).resolve()
        q: asyncio.Queue = asyncio.Queue()

        with self._lock:
            self._ensure_observer()
            self._loop = loop

            if wd_resolved != self._wd_resolved:
                self._stop_watch()
                self._wd_resolved = wd_resolved
                self._queue = q
                if self._observer is not None:
                    try:
                        self._watch = self._observer.schedule(
                            self._make_handler(), str(wd_resolved), recursive=True,
                        )
                        logger.info("file watcher → %s", wd_resolved)
                    except Exception:
                        logger.exception("failed to start watcher on %s", wd_resolved)
                        self._watch = None
            else:
                self._queue = q

        return q

    def _stop_watch(self) -> None:
        if self._watch is not None and self._observer is not None:
            try:
                self._observer.unschedule(self._watch)
            except Exception:
                pass
        self._watch = None

    def stop(self, q: asyncio.Queue) -> None:
        with self._lock:
            if self._queue is not q:
                return
            self._queue = None
            self._stop_watch()
            self._wd_resolved = None

watcher = FileWatcher()
