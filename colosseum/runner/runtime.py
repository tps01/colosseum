"""Runtime output paths, suite slots, and run-directory discovery."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from colosseum.database import DatabaseManager, initialize_database_if_needed
from colosseum.logging import setup_logging
from colosseum.results.aggregation import ResultAggregator
from colosseum.runner.run_options import resolve_outputs_root

if TYPE_CHECKING:
    from colosseum.context import RuntimeContext

_NO_ARTIFACTS_OUTPUT_ERROR = (
    "Output directory is unavailable in no-artifacts mode; "
    "disable no_artifacts or use persisted output for file artifacts."
)


def sanitize_logical_name(logical_name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]", "_", logical_name).strip("_")
    return (value or "run")[:64]


def allocate_run_directory(
    outputs_root: Path,
    logical_name: str,
    *,
    parent: Path | None = None,
) -> Path:
    base = parent if parent is not None else outputs_root
    if parent is None:
        base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_name = f"{stamp}_{sanitize_logical_name(logical_name)}"
    candidate = base / run_name
    suffix = 1
    while candidate.exists():
        candidate = base / f"{run_name}_{suffix}"
        suffix += 1
    return candidate


def rename_run_directory_for_result(output_dir: Path, overall: str) -> Path:
    normalized = overall.lower()
    if normalized not in {"pass", "fail"}:
        raise ValueError(f"Unsupported run result: {overall}")
    target_base = output_dir.with_name(f"{output_dir.name}-{normalized}")
    candidate = target_base
    suffix = 1
    while candidate.exists() and candidate != output_dir:
        candidate = target_base.with_name(f"{target_base.name}_{suffix}")
        suffix += 1
    if candidate == output_dir:
        return output_dir
    output_dir.rename(candidate)
    return candidate


def ensure_runtime_ready(ctx: RuntimeContext, logical_name: str | None = None) -> None:
    if ctx.runtime_ready:
        return
    if logical_name is None:
        logical_name = ctx.suite_name or ctx.test_case_name
    console_level = logging.DEBUG if ctx.debug_logging else logging.INFO
    if ctx.no_artifacts:
        ctx.logger = setup_logging(ctx, console=True, console_level=console_level, file=False)
        ctx.logger.debug("Runtime ready (no-artifacts mode)")
        initialize_database_if_needed(ctx)
    else:
        output_dir = allocate_run_directory(resolve_outputs_root(ctx.run_options), logical_name)
        output_dir.mkdir(parents=True, exist_ok=True)
        ctx.output_dir = output_dir
        ctx.logger = setup_logging(ctx, console=True, console_level=console_level, file=True)
        ctx.logger.debug("Allocated output directory: %s", output_dir)
        initialize_database_if_needed(ctx)
    from colosseum.config.loader import log_loaded_config

    if ctx.config is not None:
        log_loaded_config(ctx)
    for warning in ctx.config_warnings:
        if ctx.logger is not None:
            ctx.logger.warning(warning)
    ctx.runtime_ready = True


def ensure_output_dir(ctx: RuntimeContext, logical_name: str | None = None) -> Path:
    ensure_runtime_ready(ctx, logical_name)
    if ctx.no_artifacts or ctx.output_dir is None:
        raise RuntimeError(_NO_ARTIFACTS_OUTPUT_ERROR)
    return ctx.output_dir


@dataclass
class SuiteSlotResult:
    phase: str
    script_path: Path
    output_dir: Path
    test_index: int | None = None
    repeat_index: int | None = None
    affects_suite_result: bool = False
    overall: str | None = None
    exit_code: int | None = None


def ensure_suite_runtime_ready(ctx: RuntimeContext, suite_name: str) -> None:
    if ctx.suite_output_dir is not None:
        return
    console_level = logging.DEBUG if ctx.debug_logging else logging.INFO
    if ctx.no_artifacts:
        ctx.suite_output_dir = None
        ctx.logger = setup_logging(ctx, console=True, console_level=console_level, file=False)
        return
    container = allocate_run_directory(resolve_outputs_root(ctx.run_options), suite_name)
    container.mkdir(parents=True, exist_ok=True)
    ctx.suite_output_dir = container
    ctx.logger = setup_logging(ctx, console=True, console_level=console_level, file=False)
    if ctx.logger is not None:
        ctx.logger.info("Suite container: %s", container)


def begin_script_slot(
    ctx: RuntimeContext,
    logical_name: str,
    *,
    phase: str,
    affects_suite_result: bool,
) -> None:
    ctx.phase = phase
    ctx.slot_affects_suite_result = affects_suite_result
    ctx.slot_finalized = False
    ctx.test_case_name = logical_name
    ctx.result_aggregator = ResultAggregator()
    ctx.db = DatabaseManager()
    ctx.runtime_ready = False
    ctx.output_dir = None
    ctx.started_at = datetime.now(timezone.utc).astimezone()
    console_level = logging.DEBUG if ctx.debug_logging else logging.INFO
    if ctx.no_artifacts:
        ctx.logger = setup_logging(ctx, console=True, console_level=console_level, file=False)
        initialize_database_if_needed(ctx)
        ctx.runtime_ready = True
        return
    ctx.active_execution_mode = (
        "procedure"
        if phase == "test" and ctx.run_options.execution_mode == "procedure"
        else "full"
    )
    parent = ctx.suite_output_dir
    if parent is None:
        raise RuntimeError("Suite container is not allocated")
    slot_dir = allocate_run_directory(
        resolve_outputs_root(ctx.run_options),
        logical_name,
        parent=parent,
    )
    slot_dir.mkdir(parents=True, exist_ok=True)
    ctx.output_dir = slot_dir
    ctx.logger = setup_logging(ctx, console=True, console_level=console_level, file=True)
    initialize_database_if_needed(ctx)
    ctx.db.insert_run_metadata("phase", phase)
    ctx.db.insert_run_metadata("suite_name", ctx.suite_name or "")
    ctx.db.insert_event("INFO", "runner", f"phase_enter:{phase}")
    ctx.runtime_ready = True


def finalize_script_slot(
    ctx: RuntimeContext,
    *,
    script_path: Path,
    test_index: int | None = None,
    repeat_index: int | None = None,
) -> SuiteSlotResult:
    from colosseum.results.finalize import finalize_run

    if ctx.slot_finalized:
        raise RuntimeError("Script slot is already finalized")
    affects = ctx.slot_affects_suite_result
    result_data = finalize_run(ctx, mode="slot", affects_suite_result=affects)
    final_dir = ctx.output_dir or Path.cwd()
    result = SuiteSlotResult(
        phase=ctx.phase,
        script_path=script_path,
        output_dir=final_dir,
        test_index=test_index,
        repeat_index=repeat_index,
        affects_suite_result=affects,
        overall=result_data.overall if affects else None,
        exit_code=result_data.exit_code,
    )
    ctx.suite_slot_results.append(result)
    if affects:
        ctx.suite_test_results.append(result)
    ctx.output_dir = None
    ctx.runtime_ready = False
    ctx.slot_finalized = True
    console_level = logging.DEBUG if ctx.debug_logging else logging.INFO
    ctx.logger = setup_logging(ctx, console=True, console_level=console_level, file=False)
    return result


@dataclass(frozen=True)
class RunDirectoryEntry:
    path: Path
    outputs_dir: Path


def list_run_directories(cwd: Path) -> list[Path]:
    outputs_root = cwd / "outputs"
    if not outputs_root.is_dir():
        return []
    runs = [p for p in outputs_root.iterdir() if p.is_dir()]
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs


def find_output_directories(cwd: Path, *, max_depth: int = 2) -> list[Path]:
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    outputs_dirs: list[Path] = []
    seen: set[Path] = set()
    frontier = [cwd]
    for depth in range(max_depth + 1):
        for parent in frontier:
            outputs_dir = parent / "outputs"
            if outputs_dir.is_dir() and outputs_dir not in seen:
                outputs_dirs.append(outputs_dir)
                seen.add(outputs_dir)
        if depth == max_depth:
            break
        next_frontier: list[Path] = []
        for parent in frontier:
            try:
                children = sorted(
                    (path for path in parent.iterdir() if path.is_dir()),
                    key=lambda path: path.name.lower(),
                )
            except OSError:
                continue
            next_frontier.extend(path for path in children if path.name != "outputs")
        frontier = next_frontier
    return outputs_dirs


def list_run_directory_entries(cwd: Path, *, max_depth: int = 2) -> list[RunDirectoryEntry]:
    entries: list[RunDirectoryEntry] = []
    for outputs_dir in find_output_directories(cwd, max_depth=max_depth):
        for run_dir in outputs_dir.iterdir():
            if run_dir.is_dir():
                entries.append(RunDirectoryEntry(path=run_dir, outputs_dir=outputs_dir))
    entries.sort(key=lambda entry: entry.path.stat().st_mtime, reverse=True)
    return entries


def _matches_logical_name(dir_name: str, logical_name: str) -> bool:
    sanitized = sanitize_logical_name(logical_name)
    if dir_name.endswith(f"_{sanitized}"):
        return True
    pattern = rf"^.*_{re.escape(sanitized)}(?:_\d+)?(?:-(?:pass|fail)(?:_\d+)?)?$"
    return bool(re.match(pattern, dir_name))


def find_run_directory(cwd: Path, logical_name: str, since: float | None = None) -> Path | None:
    outputs_root = cwd / "outputs"
    if not outputs_root.is_dir():
        return None
    candidates: list[Path] = []
    for run_dir in outputs_root.iterdir():
        if not run_dir.is_dir():
            continue
        if since is not None and run_dir.stat().st_mtime < since:
            continue
        if _matches_logical_name(run_dir.name, logical_name):
            candidates.append(run_dir)
            continue
        try:
            children = [p for p in run_dir.iterdir() if p.is_dir()]
        except OSError:
            continue
        for child in children:
            if since is not None and child.stat().st_mtime < since:
                continue
            if _matches_logical_name(child.name, logical_name):
                candidates.append(child)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def read_summary_json(run_dir: Path) -> dict[str, Any] | None:
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        return None
    return cast("dict[str, Any]", json.loads(summary_path.read_text(encoding="utf-8")))
