from __future__ import annotations

from ..context import RuntimeContext
from .records import MeasurementRecord, RunMetadataRecord, VerificationRecord


def _ctx() -> RuntimeContext:
    from ..context import get_context

    return get_context()


_ALLOWED_TABLES = frozenset(
    {"measurements", "verifications", "commands", "events", "artifacts", "run_metadata"}
)


def is_allowed_table(name: str) -> bool:
    return name in _ALLOWED_TABLES or name.startswith("plugin_")


def read_measurements() -> list[MeasurementRecord]:
    """Return all measurement rows from the active run database.

    :returns: Measurement records from ``execution.sqlite``.
    :rtype: list[MeasurementRecord]

    :raises RuntimeError: When the database is not initialized for this run.
    """
    ctx = _ctx()
    if not ctx.db.is_initialized():
        raise RuntimeError("Database is not initialized for this run")
    return ctx.db.fetch_all_measurements()


def read_verifications() -> list[VerificationRecord]:
    """Return all verification rows from the active run database.

    :returns: Verification records from ``execution.sqlite``.
    :rtype: list[VerificationRecord]

    :raises RuntimeError: When the database is not initialized for this run.
    """
    ctx = _ctx()
    if not ctx.db.is_initialized():
        raise RuntimeError("Database is not initialized for this run")
    return ctx.db.fetch_all_verifications()


def read_run_metadata() -> list[RunMetadataRecord]:
    """Return run metadata key/value rows from the active run database.

    :returns: Metadata records (for example ``overall_status``, ``exit_code``).
    :rtype: list[RunMetadataRecord]

    :raises RuntimeError: When the database is not initialized for this run.
    """
    ctx = _ctx()
    if not ctx.db.is_initialized():
        raise RuntimeError("Database is not initialized for this run")
    return ctx.db.fetch_run_metadata()


def read_table(name: str) -> list[dict[str, object]]:
    """Return all rows from an allowed SQLite table in the active run database.

    :param name: Table name (core tables or ``plugin_*`` plugin tables).
    :type name: str

    :returns: Row dicts with column names as keys.
    :rtype: list[dict[str, object]]

    :raises RuntimeError: When the database is not initialized for this run.
    :raises ValueError: When ``name`` is not an allowed table.
    """
    ctx = _ctx()
    if not ctx.db.is_initialized():
        raise RuntimeError("Database is not initialized for this run")
    if is_allowed_table(name):
        return ctx.db.fetch_table_rows(name)
    raise ValueError(f"Unknown or disallowed table: {name}")
