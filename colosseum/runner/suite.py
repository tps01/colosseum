from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Callable

from colosseum.config.toml_relaxed import read_relaxed_toml
from colosseum.runner.run_options import RunOptions
from colosseum.runner.runtime import (
    begin_script_slot,
    ensure_suite_runtime_ready,
    finalize_script_slot,
)

if TYPE_CHECKING:
    from pathlib import Path

    from colosseum.context import RuntimeContext

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

_DURATION_RE = re.compile(
    r"^(?:(?P<days>\d+)d)?(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s?)?$",
    re.IGNORECASE,
)


@dataclass
class SuiteTestEntry:
    path: Path
    repeat_count: int = 1
    repeat_for: timedelta | None = None


@dataclass
class SuiteDefinition:
    name: str
    setup: list[Path]
    tests: list[SuiteTestEntry]
    between_tests: list[Path]
    teardown: list[Path]
    fail_fast: bool = False
    rip_cord: bool = False


@dataclass(frozen=True)
class _ScriptRunner:
    run: Callable[[Path], None]
    error_type: type[BaseException]


class SuiteError(RuntimeError):
    pass


def parse_repeat_duration(value: str) -> timedelta:
    text = value.strip()
    if not text:
        raise SuiteError("repeat_for duration must not be empty")
    match = _DURATION_RE.fullmatch(text)
    if not match or not any(match.group(n) for n in ("days", "hours", "minutes", "seconds")):
        raise SuiteError(
            f"Invalid repeat_for duration {value!r}; use suffixes s, m, h, d (e.g. 30s, 24h)",
        )
    return timedelta(
        days=int(match.group("days") or 0),
        hours=int(match.group("hours") or 0),
        minutes=int(match.group("minutes") or 0),
        seconds=int(match.group("seconds") or 0),
    )


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


def _parse_test_entry(item: object, base_dir: Path, *, index: int) -> SuiteTestEntry:
    if isinstance(item, str):
        return SuiteTestEntry(path=(base_dir / item).resolve())
    if not isinstance(item, dict):
        raise SuiteError(f"Suite tests[{index}] must be a path string or inline table")
    path = item.get("path")
    if not path or not isinstance(path, str):
        raise SuiteError(f"Suite tests[{index}] table requires string field `path`")
    resolved = (base_dir / path).resolve()
    repeat_count = item.get("repeat_count")
    repeat_for = item.get("repeat_for")
    if repeat_count is not None and repeat_for is not None:
        raise SuiteError(f"Suite tests[{index}] cannot set both repeat_count and repeat_for")
    if repeat_count is not None:
        if not isinstance(repeat_count, int) or isinstance(repeat_count, bool):
            raise SuiteError(f"Suite tests[{index}] repeat_count must be an integer")
        if repeat_count < 1:
            raise SuiteError(f"Suite tests[{index}] repeat_count must be >= 1")
        return SuiteTestEntry(path=resolved, repeat_count=repeat_count)
    if repeat_for is not None:
        if not isinstance(repeat_for, str):
            raise SuiteError(f"Suite tests[{index}] repeat_for must be a string")
        return SuiteTestEntry(path=resolved, repeat_for=parse_repeat_duration(repeat_for))
    return SuiteTestEntry(path=resolved)


def _parse_tests(value: object, base_dir: Path) -> list[SuiteTestEntry]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SuiteError("Suite field `tests` must be a list")
    return [_parse_test_entry(item, base_dir, index=index) for index, item in enumerate(value)]


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
    base = suite_path.parent
    tests = _parse_tests(raw.get("tests"), base)
    if not tests:
        raise SuiteError("Suite TOML requires non-empty `tests` list")
    for entry in tests:
        if not entry.path.exists():
            raise SuiteError(f"Test script not found: {entry.path}")
    setup = _as_path_list(raw.get("setup"), "setup", base)
    between_tests = _as_path_list(raw.get("between_tests"), "between_tests", base)
    teardown = _as_path_list(raw.get("teardown"), "teardown", base)
    for script_path in setup + between_tests + teardown:
        if not script_path.exists():
            raise SuiteError(f"Suite script not found: {script_path}")
    return SuiteDefinition(
        name=name,
        setup=setup,
        tests=tests,
        between_tests=between_tests,
        teardown=teardown,
        fail_fast=_as_bool(raw.get("fail_fast"), "fail_fast"),
        rip_cord=_as_bool(raw.get("rip_cord"), "rip_cord"),
    )


def _stop_remaining_tests(ctx: RuntimeContext, test_path: Path, reason: str) -> None:
    if ctx.db.is_initialized():
        ctx.db.insert_run_metadata("fail_fast_stopped", "1")
        ctx.db.insert_event("INFO", "runner", f"fail_fast_stop:{test_path}:{reason}")
    if ctx.logger is not None:
        ctx.logger.error("fail_fast: stopping remaining tests after %s (%s)", test_path, reason)


def _repeat_exhausted(
    entry: SuiteTestEntry, repeat_index: int, deadline: float | None,
) -> bool:
    if repeat_index == 0:
        return False
    if entry.repeat_for is not None:
        return deadline is not None and time.monotonic() >= deadline
    return repeat_index >= entry.repeat_count


def _run_script_slot(
    suite: SuiteDefinition,
    ctx: RuntimeContext,
    script: Path,
    runner: _ScriptRunner,
    *,
    phase: str,
    affects_suite_result: bool,
    test_index: int | None = None,
    repeat_index: int | None = None,
    entry: SuiteTestEntry | None = None,
) -> tuple[bool, bool]:
    """Run one script slot. Returns (rip_cord_abort, fail_fast_stop)."""
    begin_script_slot(ctx, script.stem, phase=phase, affects_suite_result=affects_suite_result)
    ctx.slot_script_path = script
    ctx.slot_test_index = test_index
    ctx.slot_repeat_index = repeat_index

    if test_index is not None and repeat_index is not None and entry is not None:
        repeat_meta = {"test_index": str(test_index), "test_repeat_index": str(repeat_index)}
        if entry.repeat_for is not None:
            repeat_meta.update(
                repeat_mode="duration",
                repeat_limit=str(int(entry.repeat_for.total_seconds())),
            )
        elif entry.repeat_count > 1:
            repeat_meta.update(repeat_mode="count", repeat_limit=str(entry.repeat_count))
        for key, value in repeat_meta.items():
            ctx.db.insert_run_metadata(key, value)
        ctx.db.insert_event(
            "INFO",
            "runner",
            f"test_repeat_start:{script}:test={test_index}:repeat={repeat_index}",
        )

    script_crash = False
    try:
        runner.run(script)
    except runner.error_type:
        script_crash = True
        ctx.result_aggregator.mark_suite_error(f"{phase} script failed")

    slot_has_failure = script_crash or not ctx.result_aggregator.overall_pass()
    if suite.rip_cord and slot_has_failure:
        ctx.rip_cord_triggered = True
    rip_abort = suite.rip_cord and slot_has_failure

    stop_fail_fast = False
    if affects_suite_result and suite.fail_fast and slot_has_failure:
        _stop_remaining_tests(ctx, script, "script_error" if script_crash else "required_failure")
        stop_fail_fast = True

    if not ctx.slot_finalized:
        finalize_script_slot(
            ctx, script_path=script, test_index=test_index, repeat_index=repeat_index,
        )
    return rip_abort, stop_fail_fast


def _run_phase_scripts(
    suite: SuiteDefinition,
    ctx: RuntimeContext,
    scripts: list[Path],
    runner: _ScriptRunner,
    *,
    phase: str,
    affects_suite_result: bool,
) -> tuple[bool, bool]:
    for script in scripts:
        rip_abort, stop_fail_fast = _run_script_slot(
            suite,
            ctx,
            script,
            runner,
            phase=phase,
            affects_suite_result=affects_suite_result,
        )
        if rip_abort or stop_fail_fast:
            return rip_abort, stop_fail_fast
    return False, False


def _run_test_schedule(
    suite: SuiteDefinition, ctx: RuntimeContext, runner: _ScriptRunner,
) -> bool:
    for test_index, entry in enumerate(suite.tests):
        deadline = (
            time.monotonic() + entry.repeat_for.total_seconds()
            if entry.repeat_for is not None
            else None
        )
        repeat_index = 0
        while not _repeat_exhausted(entry, repeat_index, deadline):
            rip_abort, stop_fail_fast = _run_script_slot(
                suite,
                ctx,
                entry.path,
                runner,
                phase="test",
                affects_suite_result=True,
                test_index=test_index,
                repeat_index=repeat_index,
                entry=entry,
            )
            repeat_index += 1
            if rip_abort or stop_fail_fast:
                return True
            another_in_entry = (
                entry.repeat_for is not None and time.monotonic() < deadline  # type: ignore[operator]
            ) or repeat_index < entry.repeat_count
            if (another_in_entry or test_index + 1 < len(suite.tests)) and suite.between_tests:
                between_rip, _ = _run_phase_scripts(
                    suite,
                    ctx,
                    suite.between_tests,
                    runner,
                    phase="between_tests",
                    affects_suite_result=False,
                )
                if between_rip:
                    return True
            if not another_in_entry:
                break
    return False


def run_suite(
    suite_path: Path,
    config_path: Path | None = None,
    metadata_path: Path | None = None,
    *,
    debug: bool = False,
    no_artifacts: bool = False,
    run_options: RunOptions | None = None,
) -> int:
    from colosseum.config import load_config
    from colosseum.config.metadata import load_metadata
    from colosseum.context import get_context, init_context
    from colosseum.results.exit_policy import finalize_suite
    from colosseum.runner.run_options import RunOptions

    from .single_test import ScriptRunError, run_script

    suite = load_suite_toml(suite_path)
    options = run_options or RunOptions()
    init_context(
        test_case_name=suite.name,
        suite_name=suite.name,
        config_path=config_path.resolve() if config_path else None,
        metadata_path=metadata_path.resolve() if metadata_path else None,
        no_artifacts=no_artifacts,
        run_options=options,
    )
    ctx = get_context()
    ctx.debug_logging = debug
    if config_path:
        load_config(config_path, metadata_path=metadata_path)
    elif metadata_path:
        load_metadata(metadata_path)

    ensure_suite_runtime_ready(ctx, suite.name)
    runner = _ScriptRunner(run_script, ScriptRunError)
    if ctx.logger is not None:
        ctx.logger.debug(
            "Suite %r: setup=%d tests=%d between=%d teardown=%d fail_fast=%s rip_cord=%s",
            suite.name,
            len(suite.setup),
            len(suite.tests),
            len(suite.between_tests),
            len(suite.teardown),
            suite.fail_fast,
            suite.rip_cord,
        )

    rip_abort = False
    if suite.setup:
        rip_abort, _ = _run_phase_scripts(
            suite,
            ctx,
            suite.setup,
            runner,
            phase="setup",
            affects_suite_result=False,
        )
    if not rip_abort:
        rip_abort = _run_test_schedule(suite, ctx, runner)
    if suite.teardown:
        _run_phase_scripts(
            suite,
            ctx,
            suite.teardown,
            runner,
            phase="teardown",
            affects_suite_result=False,
        )

    raise SystemExit(finalize_suite(ctx))
