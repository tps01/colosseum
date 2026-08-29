from __future__ import annotations

import atexit
import logging
import sys
from contextlib import suppress
from types import TracebackType
from typing import NoReturn

from ..context import RuntimeContext, get_context
from ..output import ensure_runtime_ready, rename_run_directory_for_result
from ..resource_cache import close_cached_resources

_ORIGINAL_EXCEPTHOOK = sys.excepthook
_AUTO_FINALIZE_HOOKS_REGISTERED = False


def _close_logger_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
    logger.handlers.clear()


def _finalize_context(ctx: RuntimeContext) -> int:
    ensure_runtime_ready(ctx)
    code = ctx.result_aggregator.exit_code()
    overall = "PASS" if code == 0 else "FAIL"
    if ctx.logger is not None:
        counts = ctx.result_aggregator.counts()
        ctx.logger.debug(
            "Finalizing run: verifications=%d required=%s optional=%s "
            "suite_error=%s teardown_failed=%s",
            counts["total"],
            counts["required"],
            counts["optional"],
            ctx.result_aggregator.suite_error,
            ctx.result_aggregator.teardown_failed,
        )
    ctx.db.insert_run_metadata("overall_status", overall)
    ctx.db.insert_run_metadata("exit_code", str(code))
    if ctx.logger is not None:
        ctx.logger.debug("Running plugin shutdown hooks")
    ctx.plugin_registry.run_shutdown()
    close_cached_resources(ctx.resource_cache, (("",),), logger=ctx.logger)
    measurement_count = 0
    command_count = 0
    verifications = []
    measurements = []
    if ctx.db.is_initialized():
        measurement_count = ctx.db.count_rows("measurements")
        command_count = ctx.db.count_rows("commands")
        verifications = ctx.db.fetch_all_verifications()
        measurements = ctx.db.fetch_all_measurements()
    ctx.db.flush()
    if ctx.logger is not None:
        ctx.logger.info("Overall result: %s (exit %s)", overall, code)
        _close_logger_handlers(ctx.logger)
    ctx.db.close()
    if ctx.output_dir is not None:
        from ..summary.wats import write_wats_report
        from ..summary.writer import SummaryWriter

        ctx.output_dir = rename_run_directory_for_result(ctx.output_dir, overall)
        SummaryWriter().write(
            ctx.output_dir,
            ctx.result_aggregator,
            ctx,
            measurement_count=measurement_count,
            command_count=command_count,
        )
        write_wats_report(
            ctx.output_dir, ctx, ctx.result_aggregator, verifications, measurements
        )
    ctx.finalized = True
    ctx.final_exit_code = code
    return code


def finalize_suite(ctx: RuntimeContext) -> int:
    """Finalize a suite container after all script slots have completed."""
    from ..summary.suite_writer import SuiteSummaryWriter

    writer = SuiteSummaryWriter()
    code = writer.suite_exit_code(ctx)
    overall = "PASS" if code == 0 else "FAIL"

    if ctx.logger is not None:
        ctx.logger.info("Suite overall result: %s (exit %s)", overall, code)

    ctx.plugin_registry.run_shutdown()
    close_cached_resources(ctx.resource_cache, (("",),), logger=ctx.logger)

    if ctx.logger is not None:
        _close_logger_handlers(ctx.logger)

    if ctx.suite_output_dir is not None and not ctx.no_artifacts:
        writer.write(ctx.suite_output_dir, ctx, exit_code=code, overall=overall)
        ctx.suite_output_dir = rename_run_directory_for_result(ctx.suite_output_dir, overall)

    ctx.suite_finalized = True
    ctx.finalized = True
    ctx.final_exit_code = code
    return code


def _auto_finalize_active_context() -> None:
    try:
        ctx = get_context()
    except RuntimeError:
        return
    if ctx.finalized or not ctx.auto_finalize:
        return
    try:
        _finalize_context(ctx)
    except Exception as exc:  # pragma: no cover - process-exit last resort
        print(f"Colosseum auto-finalization failed: {exc}", file=sys.stderr)


def _handle_unhandled_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    try:
        ctx = get_context()
    except RuntimeError:
        ctx = None
    if ctx is not None and not ctx.finalized and ctx.auto_finalize:
        ctx.result_aggregator.mark_suite_error(f"unhandled exception: {exc_value}")
        if ctx.db.is_initialized():
            with suppress(Exception):
                ctx.db.insert_event("ERROR", "runner", f"unhandled_exception:{exc_value}")
    _ORIGINAL_EXCEPTHOOK(exc_type, exc_value, exc_traceback)


def register_auto_finalize_hooks() -> None:
    global _AUTO_FINALIZE_HOOKS_REGISTERED

    if _AUTO_FINALIZE_HOOKS_REGISTERED:
        return
    sys.excepthook = _handle_unhandled_exception
    atexit.register(_auto_finalize_active_context)
    _AUTO_FINALIZE_HOOKS_REGISTERED = True


def endex() -> None:
    """Finalize the active run.

    During a suite run, finalizes the current script slot and returns without
    exiting the process. For single-test runs, exits with the aggregate code.
    """
    try:
        ctx = get_context()
    except RuntimeError:
        raise SystemExit(1) from None

    if ctx.finalized:
        raise SystemExit(ctx.final_exit_code if ctx.final_exit_code is not None else 1)

    if ctx.suite_output_dir is not None and not ctx.suite_finalized:
        from ..output.suite_slots import finalize_script_slot

        if ctx.slot_finalized:
            return
        if ctx.slot_script_path is None:
            raise SystemExit(1)
        finalize_script_slot(
            ctx,
            script_path=ctx.slot_script_path,
            test_index=ctx.slot_test_index,
            repeat_index=ctx.slot_repeat_index,
        )
        return

    code = _finalize_context(ctx)
    raise SystemExit(code)


def endex_process_exit() -> NoReturn:
    """Legacy alias: finalize and always exit the process."""
    endex()
    raise SystemExit(1)
