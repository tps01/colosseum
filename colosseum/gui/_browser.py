"""GUI run browser helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from colosseum.runner.runtime import (
    RunDirectoryEntry,
    list_run_directory_entries,
    read_summary_json,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class RunBrowserRow:
    entry: RunDirectoryEntry
    status: str
    mtime: float


@dataclass(frozen=True)
class RunBrowserSnapshot:
    rows: list[RunBrowserRow]

    @property
    def output_dirs(self) -> set[Path]:
        return {row.entry.outputs_dir for row in self.rows}


@dataclass(frozen=True)
class RunSnapshot:
    run_dir: Path
    log_text: str | None = None
    log_error: str | None = None
    summary: dict[str, Any] | None = None


def load_run_browser_snapshot(cwd: Path, *, max_depth: int = 2) -> RunBrowserSnapshot:
    rows: list[RunBrowserRow] = []
    for entry in list_run_directory_entries(cwd, max_depth=max_depth):
        try:
            mtime = entry.path.stat().st_mtime
        except OSError:
            continue
        try:
            summary = read_summary_json(entry.path)
        except (OSError, ValueError, json.JSONDecodeError):
            summary = None
        status = "incomplete" if summary is None else str(summary.get("overall_result", "?"))
        rows.append(RunBrowserRow(entry=entry, status=status, mtime=mtime))
    return RunBrowserSnapshot(rows=rows)


def load_run_snapshot(run_dir: Path) -> RunSnapshot:
    log_text: str | None = None
    log_error: str | None = None
    log_path = run_dir / "debug.log"
    if not log_path.is_file():
        log_error = f"No debug.log in {run_dir.name}."
    else:
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log_error = f"Cannot read debug.log: {exc}"
    try:
        summary = read_summary_json(run_dir)
    except (OSError, ValueError, json.JSONDecodeError):
        summary = None
    return RunSnapshot(run_dir=run_dir, log_text=log_text, log_error=log_error, summary=summary)


def format_summary_text(summary: dict[str, Any] | None) -> str:
    if summary is None:
        return "No summary.json (run incomplete or in progress)."
    counts = summary.get("verification_counts") or {}
    lines = [
        f"Overall: {summary.get('overall_result', '?')} (exit {summary.get('exit_code')})",
        f"Test case: {summary.get('test_case')}",
        f"Suite: {summary.get('suite')}",
        f"Config: {summary.get('config_path')}",
        f"Output: {summary.get('output_directory')}",
        f"End time: {summary.get('end_time_utc')}",
        f"Measurements: {summary.get('measurement_count')}",
        f"Verifications (required): {counts.get('required', {})}",
        f"Verifications (optional): {counts.get('optional', {})}",
    ]
    failed = summary.get("failed_required_verifications") or []
    if failed:
        lines.append("")
        lines.append("Failed required verifications:")
        for row in failed:
            lines.append(
                f"  - {row.get('status')} {row.get('domain')}.{row.get('command')} "
                f"key={row.get('key')}: {row.get('message')}",
            )
    return "\n".join(lines)
