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
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
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
  context_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
  generation_status TEXT NOT NULL DEFAULT 'complete'
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
  conversation_id TEXT, created_at TEXT NOT NULL, resolved_at TEXT, executed_at TEXT,
  agent_run_id TEXT, display_json TEXT NOT NULL DEFAULT '{}'
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
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_relationships (
  id TEXT PRIMARY KEY, source_memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  target_memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL, weight REAL NOT NULL, evidence_json TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(source_memory_id, target_memory_id, relationship_type)
);
CREATE INDEX IF NOT EXISTS idx_memory_relationships_source ON memory_relationships(source_memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_relationships_target ON memory_relationships(target_memory_id);
CREATE TABLE IF NOT EXISTS memory_embeddings (
  memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
  provider TEXT NOT NULL, model TEXT NOT NULL, dimensions INTEGER NOT NULL,
  vector_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_candidates (
  id TEXT PRIMARY KEY, content TEXT NOT NULL, category TEXT NOT NULL, memory_type TEXT NOT NULL,
  confidence REAL NOT NULL, importance INTEGER NOT NULL, source_type TEXT NOT NULL,
  source_reference TEXT, source_message_id TEXT, status TEXT NOT NULL DEFAULT 'candidate',
  dedupe_status TEXT NOT NULL DEFAULT 'new', related_memory_id TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, reason TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS conversation_summaries (
  conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
  summary TEXT NOT NULL, message_count INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversation_states (
  conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
  state_json TEXT NOT NULL, rendered_text TEXT NOT NULL,
  source_message_count INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message_feedback (
  id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  rating INTEGER NOT NULL CHECK(rating IN (-1,1)), correction TEXT,
  created_at TEXT NOT NULL, UNIQUE(message_id)
);
CREATE TABLE IF NOT EXISTS agent_runs (
  id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  status TEXT NOT NULL, step_count INTEGER NOT NULL DEFAULT 0, max_steps INTEGER NOT NULL DEFAULT 5,
  messages_json TEXT NOT NULL, context_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS agent_run_steps (
  id TEXT PRIMARY KEY, agent_run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
  step_index INTEGER NOT NULL, kind TEXT NOT NULL, tool_name TEXT, status TEXT NOT NULL,
  input_json TEXT NOT NULL DEFAULT '{}', result_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_run_steps_run ON agent_run_steps(agent_run_id, step_index);
CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS processing_jobs (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, entity_id TEXT NOT NULL, status TEXT NOT NULL,
  error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_profiles (
  id TEXT PRIMARY KEY, profile_name TEXT NOT NULL UNIQUE, provider TEXT NOT NULL,
  status TEXT NOT NULL, fingerprint TEXT, reference_count INTEGER NOT NULL DEFAULT 0,
  total_duration_seconds REAL NOT NULL DEFAULT 0, manifest_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_settings (
  key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_sessions_metadata (
  id TEXT PRIMARY KEY, conversation_id TEXT, status TEXT NOT NULL,
  turn_count INTEGER NOT NULL DEFAULT 0, started_at TEXT NOT NULL,
  ended_at TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS web_sources (
  id TEXT PRIMARY KEY, conversation_id TEXT, message_id TEXT, query TEXT,
  title TEXT NOT NULL, url TEXT NOT NULL, domain TEXT NOT NULL,
  published_at TEXT, retrieved_at TEXT NOT NULL, excerpt TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_web_sources_conversation ON web_sources(conversation_id, retrieved_at);
CREATE TABLE IF NOT EXISTS browser_sites (
  site TEXT PRIMARY KEY, status TEXT NOT NULL, profile_path TEXT NOT NULL,
  authenticated INTEGER NOT NULL DEFAULT 0, capabilities_json TEXT NOT NULL DEFAULT '[]',
  last_checked_at TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS browser_sessions_metadata (
  id TEXT PRIMARY KEY, site TEXT NOT NULL, status TEXT NOT NULL,
  authenticated INTEGER NOT NULL DEFAULT 0, started_at TEXT NOT NULL,
  ended_at TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS product_candidates (
  id TEXT PRIMARY KEY, site TEXT NOT NULL, title TEXT NOT NULL, price TEXT,
  seller TEXT, rating TEXT, review_count TEXT, delivery TEXT, prime INTEGER NOT NULL DEFAULT 0,
  availability TEXT, url TEXT NOT NULL, variant TEXT, observed_at TEXT NOT NULL,
  raw_json TEXT NOT NULL DEFAULT '{}'
);
"""


def initialize_database(path: Path | None = None) -> None:
    from app.migrations import run_migrations

    with database(path) as connection:
        connection.executescript(SCHEMA)
        run_migrations(connection, _add_column, utc_now)


def _add_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
