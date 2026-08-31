"""Ordered, idempotent SQLite migrations for installations created by older Jarvis releases."""

from collections.abc import Callable
from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    apply: Callable[[sqlite3.Connection, Callable[..., None]], None]


def _noop(_connection: sqlite3.Connection, _add_column: Callable[..., None]) -> None:
    return None


def _v2(connection: sqlite3.Connection, add_column: Callable[..., None]) -> None:
    add_column(connection, "messages", "generation_status", "TEXT NOT NULL DEFAULT 'complete'")
    add_column(connection, "pending_actions", "executed_at", "TEXT")
    add_column(connection, "pending_actions", "agent_run_id", "TEXT")


def _v4(connection: sqlite3.Connection, add_column: Callable[..., None]) -> None:
    add_column(connection, "memories", "memory_type", "TEXT NOT NULL DEFAULT 'semantic'")
    add_column(connection, "memories", "status", "TEXT NOT NULL DEFAULT 'active'")
    add_column(connection, "memories", "confidence", "REAL NOT NULL DEFAULT 1.0")
    add_column(connection, "memories", "supersedes_id", "TEXT")
    add_column(connection, "memories", "source_message_id", "TEXT")
    add_column(connection, "documents", "use_for_rag", "INTEGER NOT NULL DEFAULT 1")
    add_column(connection, "documents", "collection", "TEXT")
    connection.execute(
        "UPDATE memories SET memory_type=CASE category "
        "WHEN 'preference' THEN 'preference' WHEN 'person' THEN 'person' WHEN 'project' THEN 'project' "
        "WHEN 'decision' THEN 'decision' WHEN 'routine' THEN 'procedural' ELSE 'semantic' END "
        "WHERE memory_type IS NULL OR memory_type='semantic'"
    )


def _v7(connection: sqlite3.Connection, add_column: Callable[..., None]) -> None:
    # Compatibility repair for databases whose historical version marker was
    # written before every additive column had landed in that release.
    add_column(connection, "messages", "generation_status", "TEXT NOT NULL DEFAULT 'complete'")
    add_column(connection, "pending_actions", "executed_at", "TEXT")
    add_column(connection, "pending_actions", "agent_run_id", "TEXT")
    add_column(connection, "memories", "memory_type", "TEXT NOT NULL DEFAULT 'semantic'")
    add_column(connection, "memories", "status", "TEXT NOT NULL DEFAULT 'active'")
    add_column(connection, "memories", "confidence", "REAL NOT NULL DEFAULT 1.0")
    add_column(connection, "memories", "supersedes_id", "TEXT")
    add_column(connection, "memories", "source_message_id", "TEXT")
    add_column(connection, "documents", "use_for_rag", "INTEGER NOT NULL DEFAULT 1")
    add_column(connection, "documents", "collection", "TEXT")
    add_column(connection, "product_candidates", "asin", "TEXT")
    add_column(connection, "product_candidates", "canonical_url", "TEXT")
    add_column(connection, "product_candidates", "price_amount", "TEXT")
    add_column(connection, "product_candidates", "price_currency", "TEXT")
    add_column(connection, "memory_candidates", "reason", "TEXT NOT NULL DEFAULT ''")
    add_column(connection, "pending_actions", "display_json", "TEXT NOT NULL DEFAULT '{}'")


MIGRATIONS = (
    Migration(1, "initial schema", _noop),
    Migration(2, "streaming status and action execution timestamp", _v2),
    Migration(3, "cognitive core memory relationships", _noop),
    Migration(4, "intelligence engine, memory 2.0, feedback and agent runs", _v4),
    Migration(5, "local voice engine profiles, settings and session metadata", _noop),
    Migration(6, "web intelligence evidence and isolated browser agent metadata", _noop),
    Migration(7, "fase 3.1 hardening, structured state and browser candidate integrity", _v7),
)


def run_migrations(connection: sqlite3.Connection, add_column: Callable[..., None], now: Callable[[], str]) -> None:
    applied = {row[0] for row in connection.execute("SELECT version FROM schema_version")}
    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        migration.apply(connection, add_column)
        connection.execute(
            "INSERT INTO schema_version (version,applied_at,description) VALUES (?,?,?)",
            (migration.version, now(), migration.description),
        )
    # Re-run the latest purely additive migration to repair schema drift in
    # installations that already carry version 7. Every operation is guarded.
    _v7(connection, add_column)
