"""U-DB-02: typed read helpers."""

from __future__ import annotations

from colosseum.database import MeasurementRow
from colosseum.database import MeasurementRecord
import colosseum.database as read_api


def test_read_measurements_returns_typed_records(unit_runtime_context) -> None:
    ctx = unit_runtime_context
    ctx.db.insert_measurement(
        MeasurementRow(domain="equipment", command="measure_voltage", key="k1", value=3.3)
    )
    rows = read_api.read_measurements()
    assert len(rows) == 1
    assert isinstance(rows[0], MeasurementRecord)
    assert rows[0].key == "k1"
    assert rows[0].value == 3.3
