from __future__ import annotations

import runpy
from pathlib import Path

from ..context import get_context


class ScriptRunError(RuntimeError):
    pass


def _system_exit_code(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def run_script(path: Path) -> None:
    """Execute a test/setup/teardown script (calls main() only; no endex)."""
    ctx = get_context()
    resolved = path.resolve()
    ctx.db.insert_run_metadata("active_script", str(resolved))
    ctx.db.insert_event("INFO", "runner", f"script_start:{resolved}")
    if ctx.logger is not None:
        ctx.logger.info("Running script %s (phase=%s)", resolved, ctx.phase)
        ctx.logger.debug("Loading script module: %s", resolved)
    try:
        module_globals = runpy.run_path(str(resolved), run_name="colosseum.test_run")
        main_fn = module_globals.get("main")
        if not callable(main_fn):
            raise ScriptRunError(f"Script does not define callable main(): {resolved}")
        if ctx.logger is not None:
            ctx.logger.debug("Calling main() in %s", resolved)
        main_fn()
    except SystemExit as exc:
        if ctx.finalized:
            raise
        if ctx.suite_output_dir is not None and ctx.slot_finalized:
            return
        code = _system_exit_code(exc)
        message = f"script_exit:{resolved}: code={code}"
        ctx.db.insert_event("ERROR", "runner", message)
        if ctx.logger is not None:
            ctx.logger.error("Script exited before col.endex(): %s (code=%s)", resolved, code)
        raise ScriptRunError(message) from exc
    except Exception as exc:
        ctx.db.insert_event("ERROR", "runner", f"script_fail:{resolved}: {exc}")
        if ctx.logger is not None:
            ctx.logger.exception("Script failed: %s", resolved)
        raise ScriptRunError(str(exc)) from exc
    ctx.db.insert_event("INFO", "runner", f"script_done:{resolved}")
    if ctx.logger is not None:
        ctx.logger.debug("Script finished: %s", resolved)
