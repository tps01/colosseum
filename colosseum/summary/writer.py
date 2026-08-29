from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from colosseum.context import RuntimeContext
    from colosseum.results.aggregation import OutcomeRecord, ResultAggregator
    from colosseum.runner.runtime import SuiteSlotResult


def _count_by_kind(
    records: list[OutcomeRecord], *, kind: str, optional: bool,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in records:
        if row.get("kind") != kind or bool(row.get("optional")) != optional:
            continue
        status = row["status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def _outcome_lines(rows: list[OutcomeRecord], *, header: str) -> list[str]:
    if not rows:
        return []
    lines = ["", header]
    for row in rows:
        if header.startswith("Failed"):
            label = row.get("key") or row.get("command") or "?"
            lines.append(
                f"  - [{row.get('kind', 'outcome')}] {row.get('domain', '')}."
                f"{row.get('command', '')} key={label}: {row.get('message', '')}",
            )
        else:
            lines.append(
                f"  - [{row.get('kind')}] {row.get('domain')}.{row.get('command')} "
                f"key={row.get('key')}: {row['status']}",
            )
    return lines


def _count_lines(label: str, prefix: str, counts: dict[str, int]) -> list[str]:
    if not counts:
        return []
    lines = [f"{label}: {sum(counts.values())}"]
    lines.extend(f"  {prefix} {status}: {count}" for status, count in sorted(counts.items()))
    return lines


def _slot_dict(slot: SuiteSlotResult) -> dict[str, object]:
    return {
        "phase": slot.phase,
        "script": str(slot.script_path),
        "output_directory": str(slot.output_dir),
        "test_index": slot.test_index,
        "repeat_index": slot.repeat_index,
        "overall_result": slot.overall,
        "exit_code": slot.exit_code,
    }


class SummaryWriter:
    def write(
        self,
        output_dir: Path,
        aggregator: ResultAggregator,
        ctx: RuntimeContext,
        *,
        measurement_count: int | None = None,
        command_count: int | None = None,
    ) -> Path:
        summary_path = output_dir / "summary.txt"
        records = aggregator._records  # noqa: SLF001 — summary formatting
        required_verifications = _count_by_kind(records, kind="verification", optional=False)
        optional_verifications = _count_by_kind(records, kind="verification", optional=True)
        required_commands = _count_by_kind(records, kind="command", optional=False)
        optional_commands = _count_by_kind(records, kind="command", optional=True)
        failed_required = aggregator.failed_required_outcomes()

        if measurement_count is None or command_count is None:
            if ctx.db.is_initialized():
                measurement_count = measurement_count or ctx.db.count_rows("measurements")
                command_count = command_count or ctx.db.count_rows("commands")
            else:
                measurement_count = measurement_count or 0
                command_count = command_count or 0

        lines = [
            "Colosseum Run Summary",
            "====================",
            f"Colosseum version: {ctx.framework_version}",
            f"Test case: {ctx.test_case_name}",
            f"Suite: {ctx.suite_name or 'N/A'}",
            f"Config file: {ctx.config_path or 'N/A'}",
            f"Output directory: {output_dir}",
            f"End time: {datetime.now(timezone.utc).isoformat()}",
            f"Overall result: {'PASS' if aggregator.overall_pass() else 'FAIL'}",
            f"Exit code: {aggregator.exit_code()}",
            "",
            f"Measurements: {measurement_count}",
            f"Commands: {command_count}",
            *_count_lines(
                "Verifications (required)", "required verification", required_verifications,
            ),
            *_count_lines(
                "Commands (required outcomes)", "required command", required_commands,
            ),
            *_count_lines(
                "Verifications (optional)", "optional verification", optional_verifications,
            ),
            *_count_lines(
                "Commands (optional outcomes)", "optional command", optional_commands,
            ),
            *_outcome_lines(failed_required, header="Failed required outcomes:"),
            *_outcome_lines(aggregator.optional_outcomes(), header="Optional outcomes:"),
        ]
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        payload = {
            "colosseum_version": ctx.framework_version,
            "test_case": ctx.test_case_name,
            "suite": ctx.suite_name,
            "config_path": str(ctx.config_path) if ctx.config_path else None,
            "output_directory": str(output_dir),
            "end_time_utc": datetime.now(timezone.utc).isoformat(),
            "overall_result": "PASS" if aggregator.overall_pass() else "FAIL",
            "exit_code": aggregator.exit_code(),
            "measurement_count": measurement_count,
            "command_count": command_count,
            "verification_counts": {
                "required": required_verifications,
                "optional": optional_verifications,
            },
            "command_counts": {
                "required": required_commands,
                "optional": optional_commands,
            },
            "failed_required_outcomes": [
                {
                    "kind": row.get("kind", ""),
                    "domain": row.get("domain", ""),
                    "command": row.get("command", ""),
                    "key": row.get("key", ""),
                    "status": row.get("status", ""),
                    "message": row.get("message", ""),
                }
                for row in failed_required
            ],
            "failed_required_verifications": [
                {
                    "domain": row.get("domain", ""),
                    "command": row.get("command", ""),
                    "key": row.get("key", ""),
                    "status": row.get("status", ""),
                    "message": row.get("message", ""),
                }
                for row in failed_required
                if row.get("kind") == "verification"
            ],
            "suite_error": aggregator.suite_error,
            "teardown_failed": aggregator.teardown_failed,
        }
        (output_dir / "summary.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        return summary_path


class SuiteSummaryWriter:
    def write(
        self,
        container_dir: Path,
        ctx: RuntimeContext,
        *,
        exit_code: int,
        overall: str,
    ) -> Path:
        summary_path = container_dir / "summary.txt"
        lines = [
            "Colosseum Suite Summary",
            "=======================",
            f"Colosseum version: {ctx.framework_version}",
            f"Suite: {ctx.suite_name or ctx.test_case_name}",
            f"Config file: {ctx.config_path or 'N/A'}",
            f"Output directory: {container_dir}",
            f"End time: {datetime.now(timezone.utc).isoformat()}",
            f"Overall result: {overall}",
            f"Exit code: {exit_code}",
            f"Rip cord triggered: {'yes' if ctx.rip_cord_triggered else 'no'}",
            "",
            "Test slots (determine suite pass/fail):",
        ]
        if not ctx.suite_test_results:
            lines.append("  (none)")
        for slot in ctx.suite_test_results:
            repeat = f" repeat={slot.repeat_index}" if slot.repeat_index is not None else ""
            lines.append(
                f"  - [{slot.overall}] test={slot.test_index}{repeat} "
                f"{slot.script_path.name} -> {slot.output_dir.name}",
            )
        lines.extend(["", "All script slots:"])
        if not ctx.suite_slot_results:
            lines.append("  (none)")
        for slot in ctx.suite_slot_results:
            result = slot.overall or "n/a"
            lines.append(
                f"  - {slot.phase}: {slot.script_path.name} ({result}) -> {slot.output_dir.name}",
            )
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload = {
            "colosseum_version": ctx.framework_version,
            "suite": ctx.suite_name,
            "config_path": str(ctx.config_path) if ctx.config_path else None,
            "output_directory": str(container_dir),
            "end_time_utc": datetime.now(timezone.utc).isoformat(),
            "overall_result": overall,
            "exit_code": exit_code,
            "rip_cord_triggered": ctx.rip_cord_triggered,
            "test_slots": [_slot_dict(slot) for slot in ctx.suite_test_results],
            "all_slots": [_slot_dict(slot) for slot in ctx.suite_slot_results],
        }
        (container_dir / "summary.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        return summary_path

    @staticmethod
    def suite_exit_code(ctx: RuntimeContext) -> int:
        if ctx.rip_cord_triggered:
            return 1
        if not ctx.suite_test_results:
            return 0
        if any(slot.exit_code != 0 for slot in ctx.suite_test_results):
            return 1
        return 0
