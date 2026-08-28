from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..context import RuntimeContext
from ..database import DatabaseManager, initialize_database_if_needed
from ..logging import setup_logging
from ..resource_cache import close_cached_resources
from ..results.aggregation import ResultAggregator
from .paths import allocate_run_directory, rename_run_directory_for_result


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


def _close_logger_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
    logger.handlers.clear()


def ensure_suite_runtime_ready(ctx: RuntimeContext, suite_name: str) -> None:
    """Allocate the suite container directory (no per-slot bootstrap yet)."""
    if ctx.suite_output_dir is not None:
        return
    if ctx.no_artifacts:
        ctx.suite_output_dir = None
        console_level = logging.DEBUG if ctx.debug_logging else logging.INFO
        ctx.logger = setup_logging(ctx, console=True, console_level=console_level, file=False)
        return
    container = allocate_run_directory(Path.cwd(), suite_name)
    container.mkdir(parents=True, exist_ok=True)
    ctx.suite_output_dir = container
    console_level = logging.DEBUG if ctx.debug_logging else logging.INFO
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
    """Bootstrap a fresh output slot (child folder under the suite container)."""
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

    parent = ctx.suite_output_dir
    if parent is None:
        raise RuntimeError("Suite container is not allocated")
    slot_dir = allocate_run_directory(Path.cwd(), logical_name, parent=parent)
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
    """Finalize the active script slot and record its result."""
    if ctx.slot_finalized:
        raise RuntimeError("Script slot is already finalized")

    affects = ctx.slot_affects_suite_result
    code = ctx.result_aggregator.exit_code()
    overall = "PASS" if code == 0 else "FAIL"

    measurement_count = 0
    command_count = 0
    verifications = []
    measurements = []
    if ctx.db.is_initialized():
        ctx.db.insert_run_metadata("overall_status", overall if affects else "N/A")
        ctx.db.insert_run_metadata("exit_code", str(code))
        measurement_count = ctx.db.count_rows("measurements")
        command_count = ctx.db.count_rows("commands")
        verifications = ctx.db.fetch_all_verifications()
        measurements = ctx.db.fetch_all_measurements()
        ctx.db.flush()

    if ctx.logger is not None:
        if affects:
            ctx.logger.info("Slot result: %s (exit %s)", overall, code)
        _close_logger_handlers(ctx.logger)

    if ctx.db.is_initialized():
        ctx.db.close()

    close_cached_resources(ctx.resource_cache, (("",),), logger=ctx.logger)

    final_dir = ctx.output_dir
    if final_dir is not None and affects:
        final_dir = rename_run_directory_for_result(final_dir, overall)
        from ..summary.writer import SummaryWriter
        from ..summary.wats import write_wats_report

        SummaryWriter().write(
            final_dir,
            ctx.result_aggregator,
            ctx,
            measurement_count=measurement_count,
            command_count=command_count,
        )
        write_wats_report(final_dir, ctx, ctx.result_aggregator, verifications, measurements)

    result = SuiteSlotResult(
        phase=ctx.phase,
        script_path=script_path,
        output_dir=final_dir if final_dir is not None else Path.cwd(),
        test_index=test_index,
        repeat_index=repeat_index,
        affects_suite_result=affects,
        overall=overall if affects else None,
        exit_code=code,
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
