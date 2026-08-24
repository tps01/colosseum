"""@command persistence, logging, and run aggregation."""

from __future__ import annotations

import pytest

from colosseum.decorators import CommandResult, command
from colosseum.decorators.command import COLOSSEUM_DECORATOR
from colosseum.results.aggregation import ResultAggregator


@pytest.fixture
def ctx(unit_runtime_context):
    return unit_runtime_context


@command
def _passing(*, voltage: float, key: str = "") -> float:
    return voltage


@command
def _failing(*, key: str = "") -> None:
    raise RuntimeError("bench action failed")


@command
def _logical_fail(*, key: str = "", optional: bool = False) -> CommandResult:
    return CommandResult(status="FAIL", message="not ready", optional=optional)


def test_command_records_pass_row(ctx) -> None:
    assert _passing(voltage=3.3, key="rail") == 3.3
    row = ctx.db.fetch_table_rows("commands")[-1]
    assert row["domain"] == "core"
    assert row["command"] == "_passing"
    assert row["key"] == "rail"
    assert row["status"] == "PASS"


def test_command_error_records_and_raises(ctx) -> None:
    with pytest.raises(RuntimeError, match="bench action failed"):
        _failing()
    assert ctx.result_aggregator.overall_pass() is False
    row = ctx.db.fetch_table_rows("commands")[-1]
    assert row["status"] == "ERROR"
    assert "bench action failed" in row["message"]
    events = ctx.db.fetch_table_rows("events")
    assert any(e["level"] == "ERROR" and "bench action failed" in e["message"] for e in events)


def test_optional_command_error_does_not_fail_run(ctx) -> None:
    assert _failing(optional=True) is None
    assert ctx.result_aggregator.overall_pass() is True
    row = ctx.db.fetch_table_rows("commands")[-1]
    assert row["status"] == "ERROR"
    assert row["optional"] in (1, True)
    assert "bench action failed" in row["message"]


def test_logical_fail_recorded(ctx) -> None:
    _logical_fail(key="step")
    assert ctx.result_aggregator.overall_pass() is False


def test_decorator_metadata() -> None:
    assert getattr(_passing, COLOSSEUM_DECORATOR) == "command"


def test_aggregator_exit_code_with_command_error(ctx) -> None:
    with pytest.raises(RuntimeError, match="bench action failed"):
        _failing()
    assert ResultAggregator().exit_code() == 0
    assert ctx.result_aggregator.exit_code() == 1
