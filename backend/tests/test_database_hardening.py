import concurrent.futures
import sqlite3

from app.core.database import connect, initialize_database


def test_migrations_are_sequential_and_idempotent(tmp_path):
    path = tmp_path / "upgrade.db"
    initialize_database(path)
    initialize_database(path)
    with connect(path) as connection:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_version ORDER BY version")]
        columns = {row[1] for row in connection.execute("PRAGMA table_info(product_candidates)")}
    assert versions == list(range(1, 8))
    assert {"asin", "canonical_url", "price_amount", "price_currency"}.issubset(columns)

    drifted = tmp_path / "drifted-v7.db"
    with sqlite3.connect(drifted) as connection:
        connection.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT, description TEXT)")
        connection.execute("INSERT INTO schema_version VALUES (7,'now','old marker')")
        connection.execute("CREATE TABLE pending_actions (id TEXT PRIMARY KEY,tool TEXT,input_json TEXT,status TEXT,conversation_id TEXT,created_at TEXT,resolved_at TEXT)")
    initialize_database(drifted)
    with connect(drifted) as connection:
        repaired = {row[1] for row in connection.execute("PRAGMA table_info(pending_actions)")}
    assert {"executed_at", "agent_run_id", "display_json"}.issubset(repaired)


def test_wal_busy_timeout_and_parallel_writers(tmp_path):
    path = tmp_path / "concurrent.db"
    initialize_database(path)
    with connect(path) as connection:
        connection.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, value TEXT)")
        connection.commit()
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000

    def write(index: int) -> None:
        with connect(path) as connection:
            connection.execute("INSERT INTO counter(value) VALUES (?)", (str(index),))
            connection.commit()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(40)))
    with connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM counter").fetchone()[0] == 40
