"""Unit tests for procedure and verify-only execution modes."""

from __future__ import annotations

from colosseum.database import MeasurementRow
from colosseum.decorators import VerificationResult, measurement, verification


def test_procedure_mode_skips_verification(unit_runtime_context) -> None:
    ctx = unit_runtime_context
    ctx.active_execution_mode = "procedure"

    @measurement
    def capture(*, key: str, value: float) -> float:
        return value

    @verification
    def check(*, key: str, optional: bool = False) -> VerificationResult:
        return VerificationResult(status="FAIL", message="should not run", optional=optional)

    capture(key="v", value=1.0)
    assert check(key="v") is None
    assert ctx.db.fetch_all_verifications() == []
    assert ctx.db.get_measurement("core", "capture", "v") is not None


def test_verify_only_mode_skips_measurement(unit_runtime_context) -> None:
    ctx = unit_runtime_context
    ctx.active_execution_mode = "verify_only"
    ctx.db.insert_measurement(
        MeasurementRow(
            domain="core",
            command="capture",
            key="v",
            value=2.5,
        ),
    )

    @measurement
    def capture(*, key: str, value: float) -> float:
        raise AssertionError("measurement should not run")

    @verification
    def check(*, key: str, optional: bool = False) -> VerificationResult:
        row = ctx.db.get_measurement("core", "capture", key)
        assert row is not None
        return VerificationResult(status="PASS", optional=optional, actual=row.value)

    assert capture(key="v", value=99.0) is None
    result = check(key="v")
    assert result is not None and result.status == "PASS"
