"""Test-only helpers for session-shared unit test SQLite (not production API)."""

from __future__ import annotations

import sqlite3
from typing import Union

from colosseum.database.manager import DatabaseManager

UNIT_TEST_DB_URI = "file:colosseum_unit_tests?mode=memory&cache=shared"
_UNIT_DB_TABLES = ("measurements", "verifications", "commands", "events", "run_metadata")


def connect_unit_test_db(manager: DatabaseManager, uri: str = UNIT_TEST_DB_URI) -> None:
    if manager.is_initialized():
        return
    manager._conn = sqlite3.connect(uri, uri=True)
    manager.defer_commits = True


def truncate_unit_test_db(db: Union[sqlite3.Connection, str] = UNIT_TEST_DB_URI) -> None:
    close_when_done = isinstance(db, str)
    conn = sqlite3.connect(db, uri=True) if close_when_done else db
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for table in _UNIT_DB_TABLES:
            if table in tables:
                conn.execute(f"DELETE FROM {table}")
        conn.commit()
    finally:
        if close_when_done:
            conn.close()
