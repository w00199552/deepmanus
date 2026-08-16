from __future__ import annotations

import aiosqlite
from pathlib import Path

from openmanus.db.path import get_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    workdir     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    topic_id    TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'root',
    name        TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    title       TEXT,
    model       TEXT,
    workdir     TEXT,
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_topic ON sessions(topic_id);

CREATE TABLE IF NOT EXISTS mailboxes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id        TEXT NOT NULL,
    from_agent      TEXT NOT NULL,
    to_agent        TEXT NOT NULL,
    kind            TEXT NOT NULL,
    content         TEXT,
    whiteboard_ref  TEXT,
    read            INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mailbox_recipient ON mailboxes(topic_id, to_agent);

CREATE TABLE IF NOT EXISTS whiteboard_note (
    id          TEXT PRIMARY KEY,
    topic_id    TEXT NOT NULL,
    author      TEXT NOT NULL,
    kind        TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    title       TEXT,
    content     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_wb_note_topic ON whiteboard_note(topic_id);
"""

async def init_db() -> None:
    Path(get_db_path()).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(get_db_path()) as db:
        await db.executescript(_SCHEMA)
        await db.commit()
