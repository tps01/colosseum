from __future__ import annotations

from .manager import DatabaseManager, initialize_database_if_needed
from .records import (
    CommandRow,
    MeasurementRecord,
    MeasurementRow,
    RunMetadataRecord,
    VerificationRecord,
    VerificationRow,
)

__all__ = [
    "DatabaseManager",
    "CommandRow",
    "MeasurementRow",
    "VerificationRow",
    "initialize_database_if_needed",
    "MeasurementRecord",
    "VerificationRecord",
    "RunMetadataRecord",
]


# Read API loaded lazily to avoid import cycles with context.
def __getattr__(name: str) -> object:
    if name in {"read_measurements", "read_verifications", "read_run_metadata", "read_table"}:
        from . import read as read_mod

        return getattr(read_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
