"""Import measurements and commands from a prior run directory."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from colosseum.database import CommandRow, MeasurementRow

_MEASUREMENT_COLUMNS = (
    "domain",
    "command",
    "key",
    "row_index",
    "value_json",
    "units",
    "artifact_path",
    "status",
    "timestamp",
)
_COMMAND_COLUMNS = (
    "domain",
    "command",
    "key",
    "result_json",
    "status",
    "optional",
    "message",
    "timestamp",
)


def resolve_previous_run_dir(path: Path) -> Path:
    """Resolve a prior run directory, accepting optional ``-pass`` / ``-fail`` suffix."""
    resolved = path.resolve()
    if resolved.is_dir():
        return resolved
    raise FileNotFoundError(f"Previous output directory not found: {resolved}")


def resolve_previous_db(path: Path) -> Path:
    run_dir = resolve_previous_run_dir(path)
    db_path = run_dir / "execution.sqlite"
    if not db_path.is_file():
        raise FileNotFoundError(f"execution.sqlite not found in {run_dir}")
    return db_path


def import_evidence_from_previous(ctx: object, previous_dir: Path) -> None:
    """Copy measurements and commands from a prior run into the active database."""
    from colosseum.context import RuntimeContext

    if not isinstance(ctx, RuntimeContext):
        raise TypeError("ctx must be a RuntimeContext")
    if not ctx.db.is_initialized():
        raise RuntimeError("Database must be initialized before importing evidence")

    source_db = resolve_previous_db(previous_dir)
    source = sqlite3.connect(str(source_db))
    try:
        _copy_table_rows(
            source,
            ctx,
            "measurements",
            _MEASUREMENT_COLUMNS,
            _insert_measurement_row,
        )
        _copy_table_rows(
            source,
            ctx,
            "commands",
            _COMMAND_COLUMNS,
            _insert_command_row,
        )
    finally:
        source.close()

    ctx.db.insert_run_metadata("imported_from", str(source_db.parent))


def _copy_table_rows(
    source: sqlite3.Connection,
    ctx: object,
    table: str,
    columns: tuple[str, ...],
    inserter: object,
) -> None:
    from colosseum.context import RuntimeContext

    if not isinstance(ctx, RuntimeContext):
        raise TypeError("ctx must be a RuntimeContext")
    column_sql = ", ".join(columns)
    rows = source.execute(f"SELECT {column_sql} FROM {table} ORDER BY id ASC").fetchall()  # noqa: S608
    for row in rows:
        inserter(ctx, dict(zip(columns, row, strict=True)))


def _insert_measurement_row(ctx: object, row: dict[str, object]) -> None:
    from colosseum.context import RuntimeContext

    if not isinstance(ctx, RuntimeContext):
        raise TypeError("ctx must be a RuntimeContext")
    ctx.db.insert_measurement(
        MeasurementRow(
            domain=str(row["domain"]),
            command=str(row["command"]),
            key=str(row["key"]),
            row_index=int(row["row_index"]),  # type: ignore[arg-type]
            value=_loads_json_value(row["value_json"]),
            units=row["units"],  # type: ignore[arg-type]
            artifact_path=row["artifact_path"],  # type: ignore[arg-type]
            status=str(row["status"]),
            timestamp=str(row["timestamp"]),
        ),
    )


def _insert_command_row(ctx: object, row: dict[str, object]) -> None:
    from colosseum.context import RuntimeContext

    if not isinstance(ctx, RuntimeContext):
        raise TypeError("ctx must be a RuntimeContext")
    ctx.db.insert_command(
        CommandRow(
            domain=str(row["domain"]),
            command=str(row["command"]),
            key=str(row["key"]),
            result=_loads_json_value(row["result_json"]),
            status=str(row["status"]),
            optional=bool(row["optional"]),
            message=str(row["message"] or ""),
            timestamp=str(row["timestamp"]),
        ),
    )


def _loads_json_value(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes, bytearray)):
        return json.loads(value)
    raise TypeError(f"unexpected JSON column value: {type(value)!r}")
