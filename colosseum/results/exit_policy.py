from __future__ import annotations

import atexit
import sys
from contextlib import suppress
from typing import TYPE_CHECKING

from colosseum.context import RuntimeContext, get_context
from colosseum.logging.setup import close_logger_handlers
from colosseum.runner.runtime import rename_run_directory_for_result

from .finalize import close_resource_cache, finalize_run

if TYPE_CHECKING:
    from types import TracebackType

_ORIGINAL_EXCEPTHOOK = sys.excepthook
_AUTO_FINALIZE_HOOKS_REGISTERED = False


def _finalize_context(ctx: RuntimeContext) -> int:
    result = finalize_run(ctx, mode="single", run_shutdown=True)
    ctx.finalized = True
    ctx.final_exit_code = result.exit_code
    return result.exit_code


def finalize_suite(ctx: RuntimeContext) -> int:
    """Finalize a suite container after all script slots have completed."""
    from colosseum.summary.writer import SuiteSummaryWriter

    writer = SuiteSummaryWriter()
    code = writer.suite_exit_code(ctx)
    overall = "PASS" if code == 0 else "FAIL"

    if ctx.logger is not None:
        ctx.logger.info("Suite overall result: %s (exit %s)", overall, code)

    ctx.plugin_registry.run_shutdown()
    close_resource_cache(ctx.resource_cache, logger=ctx.logger)

    if ctx.logger is not None:
        close_logger_handlers(ctx.logger)

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
    except Exception as exc:  # pragma: no cover - process-exit last resort  # noqa: BLE001
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
        from colosseum.runner.runtime import finalize_script_slot

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
