from app.core.database import database


def test_schema_has_core_tables():
    with database() as connection:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"conversations", "messages", "memories", "documents", "tasks", "activity_log"} <= names


def test_foreign_keys_are_enabled():
    with database() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

