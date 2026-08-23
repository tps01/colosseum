from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..config.toml_relaxed import read_relaxed_toml

if TYPE_CHECKING:
    from ..context import RuntimeContext

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class SuiteDefinition:
    name: str
    setup: list[Path]
    tests: list[Path]
    teardown: list[Path]
    fail_fast: bool = False


class SuiteError(RuntimeError):
    pass


def _as_path_list(value: object, field: str, base_dir: Path) -> list[Path]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SuiteError(f"Suite field `{field}` must be a list of paths")
    paths: list[Path] = []
    for item in value:
        if not isinstance(item, str):
            raise SuiteError(f"Suite field `{field}` entries must be strings")
        paths.append((base_dir / item).resolve())
    return paths


def _as_bool(value: object, field: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise SuiteError(f"Suite field `{field}` must be a boolean")
    return value


def load_suite_toml(path: Path) -> SuiteDefinition:
    suite_path = path.resolve()
    if not suite_path.exists():
        raise SuiteError(f"Suite file not found: {suite_path}")
    try:
        raw = read_relaxed_toml(suite_path)
    except UnicodeDecodeError as exc:
        raise SuiteError(f"Suite file is not valid UTF-8: {suite_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise SuiteError(f"Invalid suite TOML: {exc}") from exc

    name = raw.get("name")
    if not name or not isinstance(name, str):
        raise SuiteError("Suite TOML requires string field `name`")
    tests = _as_path_list(raw.get("tests"), "tests", suite_path.parent)
    if not tests:
        raise SuiteError("Suite TOML requires non-empty `tests` list")
    for test_path in tests:
        if not test_path.exists():
            raise SuiteError(f"Test script not found: {test_path}")
    setup = _as_path_list(raw.get("setup"), "setup", suite_path.parent)
    teardown = _as_path_list(raw.get("teardown"), "teardown", suite_path.parent)
    for script_path in setup + teardown:
        if not script_path.exists():
            raise SuiteError(f"Suite script not found: {script_path}")
    fail_fast = _as_bool(raw.get("fail_fast"), "fail_fast")
    return SuiteDefinition(
        name=name,
        setup=setup,
        tests=tests,
        teardown=teardown,
        fail_fast=fail_fast,
    )


def _set_phase(phase: str) -> None:
    from ..context import get_context

    ctx = get_context()
    ctx.phase = phase
    ctx.db.insert_run_metadata("phase", phase)
    ctx.db.insert_event("INFO", "runner", f"phase_enter:{phase}")
    if ctx.logger is not None:
        ctx.logger.info("Suite phase: %s", phase)


def _stop_remaining_tests(ctx: RuntimeContext, test_path: Path, reason: str) -> None:
    ctx.db.insert_run_metadata("fail_fast_stopped", "1")
    ctx.db.insert_event("INFO", "runner", f"fail_fast_stop:{test_path}:{reason}")
    if ctx.logger is not None:
        ctx.logger.error(
            "fail_fast: stopping remaining tests after %s (%s)",
            test_path,
            reason,
        )


def run_suite(
    suite_path: Path,
    config_path: Path | None = None,
    *,
    debug: bool = False,
    no_artifacts: bool = False,
) -> int:
    from ..config import load_config
    from ..context import get_context, init_context
    from ..output import ensure_runtime_ready
    from ..results import endex
    from .single_test import ScriptRunError, run_script

    suite = load_suite_toml(suite_path)
    init_context(
        test_case_name=suite.name,
        suite_name=suite.name,
        config_path=config_path.resolve() if config_path else None,
        no_artifacts=no_artifacts,
    )
    ctx = get_context()
    ctx.debug_logging = debug
    if config_path:
        load_config(config_path)

    logical = ctx.suite_name or ctx.test_case_name
    ensure_runtime_ready(ctx, logical_name=logical)
    ctx.db.insert_run_metadata("suite_name", suite.name)
    ctx.db.insert_run_metadata("fail_fast", "1" if suite.fail_fast else "0")
    if ctx.logger is not None:
        ctx.logger.debug(
            "Suite %r: setup=%d test=%d teardown=%d fail_fast=%s",
            suite.name,
            len(suite.setup),
            len(suite.tests),
            len(suite.teardown),
            suite.fail_fast,
        )

    setup_failed = False
    _set_phase("setup")
    for script in suite.setup:
        try:
            run_script(script)
        except ScriptRunError:
            setup_failed = True
            ctx.result_aggregator.mark_suite_error("setup script failed")
            if ctx.logger is not None:
                ctx.logger.debug("Setup failed; skipping test scripts")
            break

    if not setup_failed:
        _set_phase("test")
        for index, test_path in enumerate(suite.tests):
            ctx.db.insert_run_metadata("test_index", str(index))
            try:
                run_script(test_path)
            except ScriptRunError:
                ctx.result_aggregator.mark_suite_error("test script failed")
                if suite.fail_fast:
                    _stop_remaining_tests(ctx, test_path, "script_error")
                    break
                if ctx.logger is not None:
                    ctx.logger.error("Test script failed (continuing suite): %s", test_path)
                continue

            if suite.fail_fast and not ctx.result_aggregator.overall_pass():
                _stop_remaining_tests(ctx, test_path, "required_failure")
                break

    _set_phase("teardown")
    for script in suite.teardown:
        try:
            run_script(script)
        except ScriptRunError:
            ctx.result_aggregator.mark_teardown_failed()

    endex()
    return 0
