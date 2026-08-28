"""U-MV: @verification behavior."""

from __future__ import annotations

import sys
import types
from inspect import signature

import pytest

from colosseum.decorators._common import resolve_domain
from colosseum.decorators.command import COLOSSEUM_DECORATOR
from colosseum.decorators.measurement import measurement
from colosseum.decorators.verification import (
    VerificationResult,
    missing_measurement_result,
    verification,
)


@pytest.fixture
def ctx(unit_runtime_context):
    return unit_runtime_context


@measurement
def _capture_value(*, key: str, value: float) -> float:
    return value


@verification()
def _bool_verify(*, key: str, expected: bool, optional: bool = False) -> bool:
    return expected


@verification()
def _raises_verify(*, key: str) -> bool:
    raise RuntimeError("boom")


@pytest.mark.requirement("U-MV-02")
def test_missing_measurement_in_body_records_error(ctx) -> None:
    @verification
    def needs_measure(*, key: str, optional: bool = False) -> VerificationResult:
        row = ctx.db.get_measurement("equipment", "measure_voltage", key, row_index=0)
        if row is None:
            return missing_measurement_result(key=key, optional=optional)
        return VerificationResult(status="PASS", message="", optional=optional)

    result = needs_measure(key="rail_a")
    assert result.status == "ERROR"
    assert "no measurement" in result.message
    assert ctx.result_aggregator.overall_pass() is False


@pytest.mark.requirement("U-MV-03")
def test_optional_failure_does_not_fail_aggregate(ctx) -> None:
    result = _bool_verify(key="opt", expected=False, optional=True)
    assert result.status == "FAIL"
    assert result.message == "verification returned False"
    assert ctx.result_aggregator.overall_pass() is True


def test_missing_key_is_error(ctx) -> None:
    result = _bool_verify(key="", expected=True)
    assert result.status == "ERROR"
    assert ctx.db.count_rows("verifications", "key=?", ("<missing>",)) >= 1


def test_exception_becomes_error_status(ctx) -> None:
    result = _raises_verify(key="x")
    assert result.status == "ERROR"
    assert "boom" in result.message


def test_optional_kwarg_requires_wrapped_parameter(ctx) -> None:
    """Document contract: optional= must be accepted by the wrapped function signature."""

    @verification()
    def no_optional_param(*, key: str) -> bool:
        return False

    result = no_optional_param(key="k", optional=True)
    assert result.status == "ERROR"
    assert "optional" in result.message.lower() or "unexpected" in result.message.lower()


def test_verification_result_passthrough(ctx) -> None:
    @verification()
    def explicit(*, key: str) -> VerificationResult:
        return VerificationResult(status="FAIL", message="custom", optional=False)

    result = explicit(key="k1")
    assert result.message == "custom"
    assert ctx.result_aggregator.overall_pass() is False


def test_default_verification_result_is_required() -> None:
    assert VerificationResult(status="PASS").optional is False


def test_resolve_domain_maps_plugin_package_attribute(monkeypatch) -> None:
    plugin = types.ModuleType("acme_plugin")
    plugin.__colosseum_domain__ = "acme"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "acme_plugin", plugin)

    def sample() -> bool:
        return True

    monkeypatch.setattr(sample, "__module__", "acme_plugin.api")
    assert resolve_domain(sample) == "acme"

    monkeypatch.setattr(sample, "__module__", "local_module")
    assert resolve_domain(sample) == "core"


def test_verification_preserves_wrapped_function_metadata() -> None:
    @verification()
    def named_verification(*, key: str) -> bool:
        return True

    assert named_verification.__name__ == "named_verification"


def test_missing_measurement_result_defaults_required() -> None:
    result = missing_measurement_result(key="rail")
    assert result.optional is False
    assert signature(missing_measurement_result).parameters["optional"].default is False


def test_verification_overloads_and_annotations() -> None:
    impl = verification.__annotations__
    assert impl["_func"] == "Callable[..., Any] | None"
    assert "sources" not in impl

    if sys.version_info < (3, 11):
        pytest.skip("typing.get_overloads requires Python 3.11+")

    from typing import get_overloads

    overloads = get_overloads(verification)
    assert len(overloads) == 2
    for overload in overloads:
        assert "sources" not in overload.__annotations__


def test_decorator_metadata() -> None:
    assert getattr(_bool_verify, COLOSSEUM_DECORATOR) == "verification"


def test_bool_pass_records_verification_row(ctx) -> None:
    result = _bool_verify(key="rail", expected=True)
    assert result.status == "PASS"
    row = ctx.db.fetch_table_rows("verifications")[-1]
    assert row["key"] == "rail"
    assert row["status"] == "PASS"
    assert ctx.result_aggregator.overall_pass() is True


def test_non_bool_return_becomes_pass_with_message(ctx) -> None:
    @verification()
    def returns_text(*, key: str) -> str:
        return "ok"

    result = returns_text(key="k")
    assert result.status == "PASS"
    assert result.message == "ok"


def test_verification_reads_prior_measurement(ctx) -> None:
    _capture_value(key="rail", value=3.3)

    @verification
    def needs_measure(*, key: str, optional: bool = False) -> VerificationResult:
        row = ctx.db.get_measurement("core", "_capture_value", key, row_index=0)
        if row is None:
            return missing_measurement_result(key=key, optional=optional)
        return VerificationResult(status="PASS", message="", optional=optional)

    result = needs_measure(key="rail")
    assert result.status == "PASS"
    assert ctx.result_aggregator.overall_pass() is True


def test_expected_val_and_minimum_persisted(ctx) -> None:
    import json

    @verification()
    def with_limits(*, key: str, expected_val: float = 0.0, minimum: float = 0.0) -> bool:
        return True

    with_limits(key="rail", expected_val=3.3)
    row = ctx.db.fetch_table_rows("verifications")[-1]
    assert json.loads(row["expected_json"]) == 3.3
    assert row["compare_op"] == "GELE"

    with_limits(key="rail", minimum=1.5)
    row = ctx.db.fetch_table_rows("verifications")[-1]
    assert json.loads(row["expected_json"]) == 1.5
    assert row["compare_op"] == "GE"


def test_maximum_exact_and_log_compare_ops_persisted(ctx) -> None:
    import json

    @verification()
    def with_limits(
        *,
        key: str,
        maximum: float = 0.0,
        exact: float = 0.0,
        compare_op: str | None = None,
    ) -> bool:
        return True

    with_limits(key="le", maximum=5.0)
    row = ctx.db.fetch_table_rows("verifications")[-1]
    assert json.loads(row["expected_json"]) == 5.0
    assert row["compare_op"] == "LE"

    with_limits(key="eq", exact=10.0)
    row = ctx.db.fetch_table_rows("verifications")[-1]
    assert json.loads(row["expected_json"]) == 10.0
    assert row["compare_op"] == "EQ"

    with_limits(key="log", compare_op="LOG")
    row = ctx.db.fetch_table_rows("verifications")[-1]
    assert row["expected_json"] == "null"
    assert row["compare_op"] == "LOG"


def test_step_name_persisted(ctx) -> None:
    @verification()
    def named(*, key: str, step_name: str = "") -> bool:
        return True

    named(key="rail", step_name="Verify rail voltage")
    row = ctx.db.fetch_table_rows("verifications")[-1]
    assert row["step_name"] == "Verify rail voltage"
