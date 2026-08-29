import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.core.config import get_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or get_settings().database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def database(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    connection = connect(path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('user','assistant','tool','system')), content TEXT NOT NULL,
  context_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY, content TEXT NOT NULL, category TEXT NOT NULL, importance INTEGER NOT NULL DEFAULT 3,
  source_type TEXT NOT NULL, source_reference TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  last_used_at TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(id UNINDEXED, content, category);
CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'inbox', priority TEXT NOT NULL DEFAULT 'normal',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, due_at TEXT, completed_at TEXT,
  project TEXT, source TEXT NOT NULL DEFAULT 'manual', estimated_minutes INTEGER
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, filename TEXT NOT NULL, original_name TEXT NOT NULL, type TEXT NOT NULL, size INTEGER NOT NULL,
  status TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]', description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, chunk_count INTEGER NOT NULL DEFAULT 0, error TEXT
);
CREATE TABLE IF NOT EXISTS document_chunks (
  id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  content TEXT NOT NULL, location TEXT, position INTEGER NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
  chunk_id UNINDEXED, document_id UNINDEXED, filename UNINDEXED, content
);
CREATE TABLE IF NOT EXISTS pending_actions (
  id TEXT PRIMARY KEY, tool TEXT NOT NULL, input_json TEXT NOT NULL, status TEXT NOT NULL,
  conversation_id TEXT, created_at TEXT NOT NULL, resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS activity_log (
  id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, tool TEXT NOT NULL, input_json TEXT NOT NULL,
  result_json TEXT NOT NULL, status TEXT NOT NULL, conversation_id TEXT
);
CREATE TABLE IF NOT EXISTS usage_events (
  id TEXT PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL, input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0, estimated_cost REAL NOT NULL DEFAULT 0, timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL,
  last_seen TEXT, capabilities TEXT NOT NULL DEFAULT '[]'
);
"""


def initialize_database(path: Path | None = None) -> None:
    with database(path) as connection:
        connection.executescript(SCHEMA)

