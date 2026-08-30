from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from colosseum.context import RuntimeContext
from .schema import SCHEMA_SQL


@dataclass
class MeasurementRow:
    """Measurement write/read row. ``id`` is set when loaded from SQLite."""

    domain: str
    command: str
    key: str
    row_index: int = 0
    value: Any = None
    units: str | None = None
    artifact_path: str | None = None
    status: str = "PASS"
    timestamp: str = ""
    id: int | None = None


@dataclass
class VerificationRow:
    """Verification write/read row. ``id`` is set when loaded from SQLite."""

    domain: str
    command: str
    key: str
    expected: Any = None
    actual: Any = None
    tolerance: float | None = None
    compare_op: str | None = None
    status: str = "PASS"
    optional: bool = False
    message: str | None = ""
    step_name: str | None = None
    timestamp: str = ""
    id: int | None = None


@dataclass
class CommandRow:
    domain: str
    command: str
    key: str = ""
    result: Any = None
    status: str = "PASS"
    optional: bool = False
    message: str = ""
    timestamp: str = ""
    id: int | None = None


@dataclass
class RunMetadataRecord:
    key: str
    value: str


MeasurementRecord = MeasurementRow
VerificationRecord = VerificationRow

_ALLOWED_TABLES = frozenset(
    {"measurements", "verifications", "commands", "events", "run_metadata"},
)


def is_allowed_table(name: str) -> bool:
    return name in _ALLOWED_TABLES or name.startswith("plugin_")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cursor_rowid(cur: sqlite3.Cursor) -> int:
    rowid = cur.lastrowid
    if rowid is None:
        raise RuntimeError("INSERT did not return a row id")
    return int(rowid)


def _loads_json(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes, bytearray)):
        loaded: object = json.loads(value)
        return loaded
    raise TypeError(f"unexpected JSON column value: {type(value)!r}")


def _as_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("bool is not a numeric tolerance")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f"expected numeric tolerance, got {type(value)!r}")


def _as_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected integer column value, got {type(value)!r}")


def _measurement_from_lookup(item: tuple[object, ...]) -> MeasurementRow:
    return MeasurementRow(
        domain=str(item[0]),
        command=str(item[1]),
        key=str(item[2]),
        row_index=_as_int(item[3]),
        value=_loads_json(item[4]),
        units=item[5],  # type: ignore[arg-type]
        artifact_path=item[6],  # type: ignore[arg-type]
        status=str(item[7]),
        timestamp=str(item[8]),
        id=_as_int(item[9]) if item[9] is not None else None,
    )


def _measurement_record(item: tuple[object, ...]) -> MeasurementRecord:
    return MeasurementRecord(
        id=_as_int(item[0]),
        domain=str(item[1]),
        command=str(item[2]),
        key=str(item[3]),
        row_index=_as_int(item[4]),
        value=_loads_json(item[5]),
        units=item[6],  # type: ignore[arg-type]
        artifact_path=item[7],  # type: ignore[arg-type]
        status=str(item[8]),
        timestamp=str(item[9]),
    )


def _verification_record(item: tuple[object, ...]) -> VerificationRecord:
    return VerificationRecord(
        id=_as_int(item[0]),
        domain=str(item[1]),
        command=str(item[2]),
        key=str(item[3]),
        expected=_loads_json(item[4]),
        actual=_loads_json(item[5]),
        tolerance=_as_optional_float(_loads_json(item[6])),
        compare_op=item[7],  # type: ignore[arg-type]
        status=str(item[8]),
        optional=bool(item[9]),
        message=item[10],  # type: ignore[arg-type]
        step_name=item[11],  # type: ignore[arg-type]
        timestamp=str(item[12]),
    )


def _active_ctx() -> RuntimeContext:
    from colosseum.context import get_context

    return get_context()


def read_measurements() -> list[MeasurementRecord]:
    ctx = _active_ctx()
    if not ctx.db.is_initialized():
        raise RuntimeError("Database is not initialized for this run")
    return ctx.db.fetch_all_measurements()


def read_verifications() -> list[VerificationRecord]:
    ctx = _active_ctx()
    if not ctx.db.is_initialized():
        raise RuntimeError("Database is not initialized for this run")
    return ctx.db.fetch_all_verifications()


def read_run_metadata() -> list[RunMetadataRecord]:
    ctx = _active_ctx()
    if not ctx.db.is_initialized():
        raise RuntimeError("Database is not initialized for this run")
    return ctx.db.fetch_run_metadata()


def read_table(name: str) -> list[dict[str, object]]:
    ctx = _active_ctx()
    if not ctx.db.is_initialized():
        raise RuntimeError("Database is not initialized for this run")
    if is_allowed_table(name):
        return ctx.db.fetch_table_rows(name)
    raise ValueError(f"Unknown or disallowed table: {name}")


class DatabaseManager:
    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self.defer_commits: bool = False

    def _maybe_commit(self) -> None:
        if not self.defer_commits:
            self._require_conn().commit()

    def flush(self) -> None:
        """Commit pending writes (no-op when ``defer_commits`` is false)."""
        if self._conn is not None:
            self._conn.commit()

    def initialize(self, db_path: Path) -> None:
        if self._conn is not None:
            return
        import os

        self.defer_commits = os.environ.get("COLOSSEUM_DEFER_DB_COMMITS") == "1"
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def open_readonly(self, db_path: Path) -> None:
        if self._conn is not None:
            raise RuntimeError("Database connection already open")
        resolved = db_path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Database not found: {resolved}")
        uri = f"file:{resolved.as_posix()}?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True)
        self._conn.execute("PRAGMA query_only = ON")

    def is_initialized(self) -> bool:
        return self._conn is not None

    def close(self) -> None:
        if self._conn is not None:
            if self.defer_commits:
                self._conn.commit()
            self._conn.close()
            self._conn = None
            self.defer_commits = False

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not initialized")
        return self._conn

    def _execute_insert(self, sql: str, params: tuple[object, ...]) -> int:
        cur = self._require_conn().execute(sql, params)
        self._maybe_commit()
        return _cursor_rowid(cur)

    def insert_measurement(self, row: MeasurementRow) -> int:
        ts = row.timestamp or _utc_now()
        return self._execute_insert(
            """
            INSERT INTO measurements
            (domain, command, key, row_index, value_json, units, artifact_path, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.domain,
                row.command,
                row.key,
                row.row_index,
                json.dumps(row.value),
                row.units,
                row.artifact_path,
                row.status,
                ts,
            ),
        )

    def insert_command(self, row: CommandRow) -> int:
        ts = row.timestamp or _utc_now()
        return self._execute_insert(
            """
            INSERT INTO commands
            (domain, command, key, result_json, status, optional, message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.domain,
                row.command,
                row.key,
                json.dumps(row.result),
                row.status,
                1 if row.optional else 0,
                row.message,
                ts,
            ),
        )

    def insert_verification(self, row: VerificationRow) -> int:
        ts = row.timestamp or _utc_now()
        return self._execute_insert(
            """
            INSERT INTO verifications
            (domain, command, key, expected_json, actual_json, tolerance_json, compare_op,
             status, optional, message, step_name, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.domain,
                row.command,
                row.key,
                json.dumps(row.expected),
                json.dumps(row.actual),
                json.dumps(row.tolerance),
                row.compare_op,
                row.status,
                1 if row.optional else 0,
                row.message,
                row.step_name,
                ts,
            ),
        )

    def insert_event(self, level: str, source: str, message: str) -> int:
        return self._execute_insert(
            "INSERT INTO events(level, source, message, timestamp) VALUES (?, ?, ?, ?)",
            (level, source, message, _utc_now()),
        )

    def insert_run_metadata(self, key: str, value: str) -> None:
        self._execute_insert(
            "INSERT OR REPLACE INTO run_metadata(key, value) VALUES (?, ?)",
            (key, value),
        )

    def get_measurement(
        self, domain: str, command: str, key: str, row_index: int = 0,
    ) -> MeasurementRow | None:
        conn = self._require_conn()
        cur = conn.execute(
            """
            SELECT domain, command, key, row_index, value_json, units,
                   artifact_path, status, timestamp, id
            FROM measurements WHERE domain=? AND command=? AND key=? AND row_index=?
            ORDER BY id DESC LIMIT 1
            """,
            (domain, command, key, row_index),
        )
        item = cur.fetchone()
        if item is None:
            return None
        return _measurement_from_lookup(item)

    def list_measurements(self, domain: str, command: str, key: str) -> list[MeasurementRow]:
        conn = self._require_conn()
        cur = conn.execute(
            """
            SELECT domain, command, key, row_index, value_json, units,
                   artifact_path, status, timestamp, id
            FROM measurements WHERE domain=? AND command=? AND key=? ORDER BY id ASC
            """,
            (domain, command, key),
        )
        return [_measurement_from_lookup(item) for item in cur.fetchall()]

    def fetch_all_measurements(self) -> list[MeasurementRecord]:
        conn = self._require_conn()
        cur = conn.execute(
            """
            SELECT id, domain, command, key, row_index, value_json, units,
                   artifact_path, status, timestamp
            FROM measurements ORDER BY id ASC
            """,
        )
        return [_measurement_record(item) for item in cur.fetchall()]

    def fetch_all_verifications(self) -> list[VerificationRecord]:
        conn = self._require_conn()
        cur = conn.execute(
            """
            SELECT id, domain, command, key, expected_json, actual_json, tolerance_json,
                   compare_op, status, optional, message, step_name, timestamp
            FROM verifications ORDER BY id ASC
            """,
        )
        return [_verification_record(item) for item in cur.fetchall()]

    def fetch_run_metadata(self) -> list[RunMetadataRecord]:
        conn = self._require_conn()
        cur = conn.execute("SELECT key, value FROM run_metadata ORDER BY key ASC")
        return [RunMetadataRecord(key=item[0], value=item[1]) for item in cur.fetchall()]

    def fetch_table_rows(self, name: str) -> list[dict[str, object]]:
        import re

        if not re.match(r"^[A-Za-z0-9_]+$", name):
            raise ValueError(f"Invalid table name: {name}")
        conn = self._require_conn()
        cur = conn.execute(f"SELECT * FROM {name}")  # nosec B608  # name validated above
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def count_rows(
        self, table: str, where: str = "", params: tuple[object, ...] = (),
    ) -> int:
        import re

        if not re.match(r"^[A-Za-z0-9_]+$", table):
            raise ValueError(f"Invalid table name: {table}")
        conn = self._require_conn()
        query = f"SELECT COUNT(*) FROM {table}"  # nosec B608  # table validated above
        if where:
            query += f" WHERE {where}"
        cur = conn.execute(query, params)
        return int(cur.fetchone()[0])


def initialize_database_if_needed(ctx: RuntimeContext) -> None:
    if not ctx.db.is_initialized():
        if ctx.no_artifacts:
            db_path = Path(":memory:")
        elif ctx.output_dir is None:
            raise RuntimeError("Output directory must be allocated before DB init")
        else:
            db_path = ctx.output_dir / "execution.sqlite"
        ctx.db.initialize(db_path)
        if ctx.logger is not None:
            ctx.logger.debug("Initialized execution database: %s", db_path)
        ctx.db.insert_run_metadata("test_case_name", ctx.test_case_name)
        ctx.db.insert_run_metadata("suite_name", ctx.suite_name or "")
        ctx.db.insert_run_metadata("config_path", str(ctx.config_path) if ctx.config_path else "")
