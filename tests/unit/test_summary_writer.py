"""Summary artifact content."""

from __future__ import annotations

from colosseum.decorators.verification import VerificationResult
from colosseum.summary.writer import SummaryWriter


def test_summary_lists_failed_required(unit_runtime_context) -> None:
    ctx = unit_runtime_context
    out = ctx.output_dir
    assert out is not None
    ctx.result_aggregator.record_verification(
        VerificationResult(status="FAIL", message="out of tolerance", optional=False),
        key="rail_a",
        command="verify_voltage",
        domain="equipment",
    )
    SummaryWriter().write(out, ctx.result_aggregator, ctx)
    text = (out / "summary.txt").read_text(encoding="utf-8")
    assert "Overall result: FAIL" in text
    assert "rail_a" in text
    assert "Exit code: 1" in text
    import json

    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert payload["overall_result"] == "FAIL"
    assert payload["exit_code"] == 1
    assert payload["failed_required_verifications"][0]["key"] == "rail_a"


def test_summary_json_splits_failed_commands_from_verifications(unit_runtime_context) -> None:
    import json

    from colosseum.decorators import CommandResult

    ctx = unit_runtime_context
    out = ctx.output_dir
    assert out is not None
    ctx.result_aggregator.record_verification(
        VerificationResult(status="FAIL", message="rail low", optional=False),
        key="rail_a",
        command="verify_voltage",
        domain="equipment",
    )
    ctx.result_aggregator.record_command(
        CommandResult(status="ERROR", message="set failed", optional=False),
        key="rail_a",
        command="set_voltage",
        domain="equipment",
    )
    ctx.result_aggregator.record_verification(
        VerificationResult(status="FAIL", message="noise", optional=True),
        key="probe",
        command="verify_noise",
        domain="equipment",
    )
    SummaryWriter().write(out, ctx.result_aggregator, ctx)
    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert payload["overall_result"] == "FAIL"
    assert payload["exit_code"] == 1
    kinds = {row["kind"] for row in payload["failed_required_outcomes"]}
    assert kinds == {"verification", "command"}
    assert [row["key"] for row in payload["failed_required_verifications"]] == ["rail_a"]
    text = (out / "summary.txt").read_text(encoding="utf-8")
    assert "[verification]" in text
    assert "[command]" in text
    assert "Optional outcomes:" in text
