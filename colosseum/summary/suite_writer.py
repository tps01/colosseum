from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..context import RuntimeContext


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
            repeat = ""
            if slot.repeat_index is not None:
                repeat = f" repeat={slot.repeat_index}"
            lines.append(
                f"  - [{slot.overall}] test={slot.test_index}{repeat} "
                f"{slot.script_path.name} -> {slot.output_dir.name}"
            )

        lines.append("")
        lines.append("All script slots:")
        if not ctx.suite_slot_results:
            lines.append("  (none)")
        for slot in ctx.suite_slot_results:
            result = slot.overall or "n/a"
            lines.append(
                f"  - {slot.phase}: {slot.script_path.name} ({result}) -> {slot.output_dir.name}"
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
            "test_slots": [
                {
                    "phase": slot.phase,
                    "script": str(slot.script_path),
                    "output_directory": str(slot.output_dir),
                    "test_index": slot.test_index,
                    "repeat_index": slot.repeat_index,
                    "overall_result": slot.overall,
                    "exit_code": slot.exit_code,
                }
                for slot in ctx.suite_test_results
            ],
            "all_slots": [
                {
                    "phase": slot.phase,
                    "script": str(slot.script_path),
                    "output_directory": str(slot.output_dir),
                    "test_index": slot.test_index,
                    "repeat_index": slot.repeat_index,
                    "overall_result": slot.overall,
                    "exit_code": slot.exit_code,
                }
                for slot in ctx.suite_slot_results
            ],
        }
        json_path = container_dir / "summary.json"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
