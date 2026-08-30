"""WATS JSON report writer."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from colosseum.database.manager import MeasurementRecord, VerificationRecord
from colosseum.results.aggregation import ResultAggregator
from colosseum.summary.wats import build_wats_report, write_wats_report


def _ctx(unit_runtime_context, *, metadata: dict[str, str] | None = None):
    ctx = unit_runtime_context
    ctx.test_case_name = "example1"
    ctx.metadata_path = "/tmp/meta.yaml"
    ctx.metadata_yaml = metadata or {
        "uut": "PARTNUMBER",
        "revision": "1.2.3",
        "serial_number": "123",
        "process_code": "1234",
        "location": "TBD",
        "test_intent": "Acceptance",
        "user_name": "USERNAME",
    }
    eastern = timezone(timedelta(hours=-4))
    ctx.started_at = datetime(2026, 8, 7, 8, 40, 48, tzinfo=eastern)
    return ctx


def test_build_wats_report_one_step_per_verification(unit_runtime_context) -> None:
    ctx = _ctx(unit_runtime_context)
    aggregator = ResultAggregator()
    verifications = [
        VerificationRecord(
            domain="template",
            command="verify_bandwidth",
            key="ver_1",
            expected=6.0,
            actual=5.975,
            tolerance=1.75,
            compare_op="GELE",
            status="PASS",
        ),
        VerificationRecord(
            domain="template",
            command="verify_flag",
            key="ver_2",
            actual=None,
            status="PASS",
        ),
    ]
    ended = datetime(2026, 8, 7, 8, 41, 26, 329999, tzinfo=timezone(timedelta(hours=-4)))
    payload = build_wats_report(ctx, aggregator, verifications, ended_at=ended)
    assert payload["type"] == "T"
    assert payload["result"] == "P"
    assert payload["start"] == "2026-08-07T08:40:48-04:00"
    assert payload["pn"] == "PARTNUMBER"
    steps = payload["root"]["steps"]
    assert len(steps) == 2
    assert steps[0]["stepType"] == "ET_NLT"
    assert steps[0]["tsGuid"] == "ver_1"
    assert steps[0]["numericMeas"][0]["compOp"] == "GELE"
    assert steps[0]["numericMeas"][0]["lowLimit"] == 4.25
    assert steps[0]["numericMeas"][0]["highLimit"] == 7.75
    assert steps[1]["stepType"] == "ET_PFT"


def test_units_from_linked_measurement(unit_runtime_context) -> None:
    ctx = _ctx(unit_runtime_context)
    verifications = [
        VerificationRecord(
            domain="template",
            command="verify_voltage",
            key="ver_1",
            expected=3.3,
            actual=3.3,
            tolerance=0.0,
            compare_op="GELE",
            status="PASS",
        ),
    ]
    measurements = [
        MeasurementRecord(
            domain="template",
            command="measure_voltage",
            key="ver_1",
            units="V",
        ),
    ]
    payload = build_wats_report(ctx, ResultAggregator(), verifications, measurements)
    assert payload["root"]["steps"][0]["numericMeas"][0]["unit"] == "V"


def test_caused_failure_only_on_first_required_failure(unit_runtime_context) -> None:
    ctx = _ctx(unit_runtime_context)
    aggregator = ResultAggregator()
    verifications = [
        VerificationRecord(domain="t", command="a", key="v1", status="FAIL", optional=False),
        VerificationRecord(domain="t", command="b", key="v2", status="FAIL", optional=False),
        VerificationRecord(domain="t", command="c", key="v3", status="FAIL", optional=True),
    ]
    payload = build_wats_report(ctx, aggregator, verifications)
    steps = payload["root"]["steps"]
    assert steps[0]["causedUUTFailure"] is True
    assert steps[1]["causedUUTFailure"] is False
    assert steps[2]["causedUUTFailure"] is False


def test_error_maps_to_e(unit_runtime_context) -> None:
    ctx = _ctx(unit_runtime_context)
    aggregator = ResultAggregator()
    verifications = [
        VerificationRecord(domain="t", command="a", key="v1", status="ERROR", optional=False),
    ]
    payload = build_wats_report(ctx, aggregator, verifications)
    assert payload["result"] == "E"
    assert payload["root"]["steps"][0]["status"] == "E"


def test_string_verification_emits_et_svt(unit_runtime_context) -> None:
    ctx = _ctx(unit_runtime_context)
    verifications = [
        VerificationRecord(
            domain="t",
            command="verify_label",
            key="ver_s",
            expected="ABC",
            actual="ABC",
            status="PASS",
        ),
    ]
    payload = build_wats_report(ctx, ResultAggregator(), verifications)
    step = payload["root"]["steps"][0]
    assert step["stepType"] == "ET_SVT"
    assert step["stringMeas"][0]["compOp"] == "EQ"
    assert step["stringMeas"][0]["value"] == "ABC"


def test_compare_ops_le_eq_log(unit_runtime_context) -> None:
    ctx = _ctx(unit_runtime_context)
    verifications = [
        VerificationRecord(
            domain="t",
            command="a",
            key="le",
            expected=5.0,
            actual=4.0,
            compare_op="LE",
            status="PASS",
        ),
        VerificationRecord(
            domain="t",
            command="b",
            key="eq",
            expected=10.0,
            actual=10.0,
            compare_op="EQ",
            status="PASS",
        ),
        VerificationRecord(
            domain="t",
            command="c",
            key="log",
            expected=None,
            actual=7.5,
            compare_op="LOG",
            status="PASS",
        ),
    ]
    payload = build_wats_report(ctx, ResultAggregator(), verifications)
    steps = payload["root"]["steps"]
    assert steps[0]["numericMeas"][0]["compOp"] == "LE"
    assert steps[1]["numericMeas"][0]["compOp"] == "EQ"
    assert steps[2]["numericMeas"][0]["compOp"] == "LOG"


def test_optional_metadata_keys(unit_runtime_context) -> None:
    ctx = _ctx(
        unit_runtime_context,
        metadata={
            "uut": "PARTNUMBER",
            "revision": "1.2.3",
            "serial_number": "123",
            "process_code": "1234",
            "location": "TBD",
            "test_intent": "Acceptance",
            "user_name": "USERNAME",
            "process_name": "SW Debug",
            "report_text": "Run notes",
            "seq_version": "1.2.0",
            "batch_serial": "BATCH-1",
            "fixture_id": "FX-9",
            "comment": "hello",
            "misc_infos": [{"description": "Temp", "text": "25C", "numeric": None}],
            "sub_units": [{"partType": "PCBA", "pn": "SUB-1", "rev": "A", "sn": "SN-1"}],
        },
    )
    payload = build_wats_report(ctx, ResultAggregator(), [])
    assert payload["processName"] == "SW Debug"
    assert payload["root"]["reportText"] == "Run notes"
    assert payload["root"]["seqCall"]["version"] == "1.2.0"
    assert payload["uut"]["batchSN"] == "BATCH-1"
    assert payload["uut"]["fixtureId"] == "FX-9"
    assert payload["uut"]["comment"] == "hello"
    assert payload["miscInfos"][-1]["description"] == "Temp"
    assert payload["subUnits"][0]["pn"] == "SUB-1"


def test_minimal_metadata_shape_unchanged(unit_runtime_context) -> None:
    ctx = _ctx(unit_runtime_context)
    payload = build_wats_report(ctx, ResultAggregator(), [])
    assert payload["uut"] == {"user": "USERNAME"}
    assert "processName" not in payload
    assert "reportText" not in payload["root"]
    assert "subUnits" not in payload
    assert payload["root"]["seqCall"]["version"] == "0.0"


def test_golden_wats_example_shape(unit_runtime_context) -> None:
    ctx = _ctx(unit_runtime_context)
    ctx.test_case_name = "example1"
    verifications = [
        VerificationRecord(
            domain="template",
            command="verify_bandwidth",
            key="ver_1",
            step_name="Verify bandwidth 1",
            expected=6.0,
            actual=5.975,
            tolerance=1.75,
            compare_op="GELE",
            status="PASS",
        ),
        VerificationRecord(
            domain="template",
            command="verify_center",
            key="ver_2",
            step_name="Verify center 1",
            expected=100.0,
            actual=100.0,
            tolerance=1.0,
            compare_op="GELE",
            status="PASS",
        ),
        VerificationRecord(
            domain="template",
            command="verify_bandwidth",
            key="ver_3",
            step_name="Verify bandwidth 2",
            expected=17.5,
            actual=15.225,
            tolerance=2.7,
            compare_op="GELE",
            status="PASS",
        ),
        VerificationRecord(
            domain="template",
            command="verify_center",
            key="ver_4",
            step_name="Verify center 2",
            expected=105.0,
            actual=105.0,
            tolerance=-1.0,
            compare_op="GELE",
            status="PASS",
        ),
    ]
    ended = datetime(2026, 8, 7, 8, 41, 26, 786330, tzinfo=timezone(timedelta(hours=-4)))
    payload = build_wats_report(ctx, ResultAggregator(), verifications, ended_at=ended)
    payload["machineName"] = "HOSTNAME"
    payload["miscInfos"][0]["text"] = "TBD"
    payload["miscInfos"][1]["text"] = "TBD"
    payload["root"]["reportText"] = "Here is a report text"
    payload["root"]["totTime"] = 78.78632999999999
    golden_path = Path(__file__).resolve().parents[1] / "fixtures" / "wats_golden_example1.json"
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert payload == golden


def test_write_wats_report_creates_timestamped_json(unit_runtime_context, tmp_path: Path) -> None:
    ctx = _ctx(unit_runtime_context)
    ctx.output_dir = tmp_path
    ctx.test_case_name = "example1"
    aggregator = ResultAggregator()
    path = write_wats_report(tmp_path, ctx, aggregator, [])
    assert path is not None
    assert path.parent == tmp_path
    assert path.name.startswith("wats_")
    assert path.name.endswith("_example1.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["type"] == "T"
    assert (tmp_path / "summary.json").exists() is False


def test_write_wats_report_appends_debug_log(unit_runtime_context, tmp_path: Path) -> None:
    ctx = _ctx(unit_runtime_context)
    ctx.test_case_name = "demo"
    log_path = tmp_path / "debug.log"
    log_path.write_text("existing line\n", encoding="utf-8")
    path = write_wats_report(tmp_path, ctx, ResultAggregator(), [])
    assert path is not None
    log_text = log_path.read_text(encoding="utf-8")
    assert "Wrote WATS report:" in log_text
    assert "WATS metadata sources:" in log_text


def test_write_wats_report_best_effort_without_metadata(
    unit_runtime_context, tmp_path: Path
) -> None:
    ctx = unit_runtime_context
    ctx.output_dir = tmp_path
    ctx.test_case_name = "demo"
    ctx.metadata_path = None
    ctx.metadata_yaml = {}
    path = write_wats_report(tmp_path, ctx, ResultAggregator(), [])
    assert path is not None
    assert path.name.endswith("_demo.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["type"] == "T"
    assert data["pn"] == ""
    assert "user" in data["uut"]
