from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from openmanus.common.exceptions import TopicDeleteError
from openmanus.db import init_db
from openmanus.agents.agent_factory import (
    resolve_session_id,
    resolve_topic_id,
    compute_thread_id,
)
from openmanus.topics.store import (
    MAIN_TOPIC_ID,
    SessionStore,
    TopicStore,
    session_store,
    topic_store,
)
from openmanus.config import settings

@pytest.fixture(autouse=True)
def _isolate_db():
    saved = settings.database_url
    tmpdir = tempfile.mkdtemp(prefix="openmanus_test_")
    settings.database_url = f"sqlite:///{Path(tmpdir) / 'checkpoints.db'}"
    yield
    settings.database_url = saved

@pytest.fixture
async def db():
    await init_db()
    return topic_store

class TestComputeThreadId:

    def test_basic(self):
        assert compute_thread_id("topic-abc", "Coder") == "topic-abc:Coder"

    def test_main_topic(self):
        assert compute_thread_id("main", "Manus") == "main:Manus"

    def test_same_agent_same_topic_shares_thread(self):
        t = compute_thread_id("topic-1", "Researcher")
        assert compute_thread_id("topic-1", "Researcher") == t

    def test_different_agents_isolate(self):
        assert compute_thread_id("topic-1", "Coder") != compute_thread_id("topic-1", "Researcher")

    def test_different_topics_isolate(self):
        assert compute_thread_id("topic-1", "Coder") != compute_thread_id("topic-2", "Coder")

class TestTopicStore:
    async def test_create_and_get(self, db):
        t = await db.create(title="bfs task", workdir="/tmp/bfs")
        assert t.id.startswith("topic-")
        assert t.title == "bfs task"
        fetched = await db.get(t.id)
        assert fetched is not None
        assert fetched.title == "bfs task"

    async def test_ensure_main_creates_if_absent(self, db):
        t = await db.ensure_main()
        assert t.id == MAIN_TOPIC_ID
        assert t.title == "Main"

    async def test_ensure_main_idempotent(self, db):
        t1 = await db.ensure_main()
        t2 = await db.ensure_main()
        assert t1.id == t2.id == MAIN_TOPIC_ID

    async def test_update_workdir(self, db):
        t = await db.create(title="test", workdir="/old")
        updated = await db.update_workdir(t.id, "/new")
        assert updated.workdir == "/new"

    async def test_list(self, db):
        await db.create(title="task A")
        await db.create(title="task B")
        await db.ensure_main()
        topics = await db.list_topics()
        assert len(topics) >= 3
        titles = [t.title for t in topics]
        assert "task A" in titles
        assert "task B" in titles
        assert "Main" in titles

    async def test_delete(self, db):
        t = await db.create(title="disposable")
        assert await db.delete(t.id) is True
        assert await db.get(t.id) is None

    async def test_cannot_delete_main(self, db):
        await db.ensure_main()
        with pytest.raises(TopicDeleteError):
            await db.delete(MAIN_TOPIC_ID)
        assert await db.get(MAIN_TOPIC_ID) is not None

class TestSessionStore:
    async def test_create_requires_topic_id(self, db):
        main = await db.ensure_main()
        s = await session_store.create(topic_id=main.id, name="Manus", kind="root")
        assert s.topic_id == main.id
        assert s.name == "Manus"

    async def test_create_generates_session_id(self, db):
        main = await db.ensure_main()
        s = await session_store.create(topic_id=main.id, name="Coder")
        assert s.id.startswith("sess-")

    async def test_create_with_explicit_session_id(self, db):
        main = await db.ensure_main()
        s = await session_store.create(
            topic_id=main.id, name="Manus", session_id="custom-id"
        )
        assert s.id == "custom-id"

    async def test_get(self, db):
        main = await db.ensure_main()
        s = await session_store.create(topic_id=main.id, name="Coder")
        fetched = await session_store.get(s.id)
        assert fetched is not None
        assert fetched.name == "Coder"
        assert fetched.topic_id == main.id

    async def test_list_in_topic(self, db):
        topic_a = await db.create(title="topic A")
        topic_b = await db.create(title="topic B")
        await session_store.create(topic_id=topic_a.id, name="Coder")
        await session_store.create(topic_id=topic_a.id, name="Researcher")
        await session_store.create(topic_id=topic_b.id, name="Coder")

        in_a = await session_store.list_in_topic(topic_a.id)
        assert len(in_a) == 2
        in_b = await session_store.list_in_topic(topic_b.id)
        assert len(in_b) == 1

    async def test_list_filter_by_kind(self, db):
        main = await db.ensure_main()
        await session_store.create(topic_id=main.id, name="Coder", kind="subagent")
        await session_store.create(topic_id=main.id, name="Manus", kind="root")
        roots = await session_store.list(kind="root")
        assert all(s.kind == "root" for s in roots)
        assert len(roots) >= 1

    async def test_update_status(self, db):
        main = await db.ensure_main()
        s = await session_store.create(topic_id=main.id, name="Coder")
        updated = await session_store.update(s.id, status="running")
        assert updated.status == "running"

    async def test_delete(self, db):
        main = await db.ensure_main()
        s = await session_store.create(topic_id=main.id, name="Coder")
        assert await session_store.delete(s.id) is True
        assert await session_store.get(s.id) is None

    async def test_thread_id_from_session_row(self, db):
        topic = await db.create(title="test thread")
        s = await session_store.create(topic_id=topic.id, name="Coder")
        tid = compute_thread_id(s.topic_id, s.name)
        assert tid == f"{topic.id}:Coder"

class TestResolveConfig:

    def testresolve_session_id(self):
        config = {"configurable": {"session_id": "sess-123", "thread_id": "main:Manus"}}
        assert resolve_session_id(config) == "sess-123"

    def testresolve_session_id_missing(self):
        assert resolve_session_id({}) == "unknown"
        assert resolve_session_id(None) == "unknown"

    def testresolve_topic_id(self):
        config = {"configurable": {"topic_id": "topic-abc"}}
        assert resolve_topic_id(config) == "topic-abc"

    def testresolve_topic_id_missing(self):
        assert resolve_topic_id({}) is None
        assert resolve_topic_id(None) is None

    def test_resolve_does_not_use_thread_id(self):
        config = {"configurable": {"thread_id": "main:Manus"}}
        assert resolve_session_id(config) == "unknown"
