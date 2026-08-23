"""Characterization of runtime contracts that cleanup must preserve."""

from __future__ import annotations

import pytest

from colosseum.config.sections import ConfigSectionSpec
from colosseum.database import CommandRow, MeasurementRow, VerificationRow
from colosseum.database.read import is_allowed_table
from colosseum.plugins.registry import PluginRegistry
from colosseum.results import endex

from tests.support.helpers import run_endex_expect_code


def test_endex_runs_shutdown_hooks_then_closes_leftover_cache(
    unit_runtime_context, tmp_path
) -> None:
    ctx = unit_runtime_context
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ctx.output_dir = run_dir
    ctx.runtime_ready = True

    order: list[str] = []

    class _Cached:
        def close(self) -> None:
            order.append("cache")

    ctx.resource_cache["instrument:1"] = _Cached()
    ctx.plugin_registry.register_shutdown(lambda: order.append("hook"))

    run_endex_expect_code(0)

    assert order == ["hook", "cache"]
    assert ctx.resource_cache == {}
    assert ctx.finalized is True
    assert ctx.final_exit_code == 0


def test_endex_second_call_reuses_exit_code_without_rerunning_hooks(
    unit_runtime_context, tmp_path
) -> None:
    ctx = unit_runtime_context
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ctx.output_dir = run_dir
    ctx.runtime_ready = True

    hooks = {"count": 0}
    ctx.plugin_registry.register_shutdown(lambda: hooks.__setitem__("count", hooks["count"] + 1))

    run_endex_expect_code(0)
    run_endex_expect_code(0)

    assert hooks["count"] == 1
    with pytest.raises(SystemExit) as exc:
        endex()
    assert exc.value.code == 0


def test_config_section_specs_lists_registered_sections_in_order() -> None:
    reg = PluginRegistry()
    first = ConfigSectionSpec("acme.device", "device_id", ("driver",))
    second = ConfigSectionSpec("acme.host", "host_id", ("address",))
    reg.register_config_section(first)
    reg.register_config_section(second)
    assert reg.config_section_specs() == [first, second]


def test_is_allowed_table_accepts_core_and_plugin_prefix() -> None:
    for name in (
        "measurements",
        "verifications",
        "commands",
        "events",
        "artifacts",
        "run_metadata",
        "plugin_custom",
        "plugin_",
    ):
        assert is_allowed_table(name) is True
    assert is_allowed_table("sqlite_master") is False
    assert is_allowed_table("users") is False


def test_write_rows_round_trip_through_typed_reads(unit_runtime_context) -> None:
    import colosseum.database.read as read_api

    ctx = unit_runtime_context
    ctx.db.insert_measurement(
        MeasurementRow(
            domain="equipment",
            command="measure_voltage",
            key="rail",
            value=3.3,
            units="V",
        )
    )
    ctx.db.insert_verification(
        VerificationRow(
            domain="equipment",
            command="verify_voltage",
            key="rail",
            expected=3.3,
            actual=3.3,
            status="PASS",
        )
    )
    ctx.db.insert_command(
        CommandRow(
            domain="equipment",
            command="set_voltage",
            key="rail",
            result="ok",
            status="PASS",
        )
    )
    ctx.db.insert_run_metadata("operator", "lab")

    measurements = read_api.read_measurements()
    verifications = read_api.read_verifications()
    metadata = {row.key: row.value for row in read_api.read_run_metadata()}
    commands = read_api.read_table("commands")

    assert measurements[0].domain == "equipment"
    assert measurements[0].command == "measure_voltage"
    assert measurements[0].key == "rail"
    assert measurements[0].value == 3.3
    assert measurements[0].units == "V"
    assert measurements[0].id is not None

    assert verifications[0].key == "rail"
    assert verifications[0].status == "PASS"
    assert verifications[0].expected == 3.3
    assert verifications[0].id is not None

    assert metadata["operator"] == "lab"
    assert commands[-1]["command"] == "set_voltage"
    assert commands[-1]["key"] == "rail"

    looked_up = ctx.db.get_measurement("equipment", "measure_voltage", "rail")
    assert looked_up is not None
    assert looked_up.value == 3.3
    assert looked_up.key == "rail"
    assert looked_up.id == measurements[0].id
    assert isinstance(measurements[0], MeasurementRow)
