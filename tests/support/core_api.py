"""Small decorated API used to test the core runtime without plugins."""

from __future__ import annotations

from colosseum.context import require_context
from colosseum.decorators import VerificationResult, measurement, verification


@measurement
def measure_value(*, key: str, value: float) -> float:
    return value


@verification
def verify_value(
    *,
    key: str,
    expected_val: float,
    tolerance: float,
    optional: bool = False,
) -> VerificationResult:
    row = require_context().db.get_measurement("core", "measure_value", key)
    if row is None:
        return VerificationResult(status="ERROR", message=f"no measurement for key={key}")
    actual = float(row.value)
    passed = abs(actual - expected_val) <= tolerance
    return VerificationResult(
        status="PASS" if passed else "FAIL",
        message="" if passed else f"{actual} outside {expected_val} ± {tolerance}",
        optional=optional,
        actual=actual,
    )
