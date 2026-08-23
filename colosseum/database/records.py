from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    status: str = "PASS"
    optional: bool = False
    message: str | None = ""
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


# Public read aliases — same objects as the write rows.
MeasurementRecord = MeasurementRow
VerificationRecord = VerificationRow
