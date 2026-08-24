"""I-SUITE: run_suite phase behavior."""

from __future__ import annotations

import json

import pytest

from colosseum.runner.suite import run_suite
from tests.support.helpers import (
    latest_suite_container,
    list_slot_dirs,
    query_db,
    slot_dirs_matching,
)


def _run_suite_expect_exit(suite_path, core_config, isolated_cwd, code: int) -> None:
    with pytest.raises(SystemExit) as exc:
        run_suite(suite_path, core_config)
    assert exc.value.code == code


def _container_summary(container) -> dict:
    path = container / "summary.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _slot_with_stem(container, stem: str):
    matches = slot_dirs_matching(container, stem)
    assert matches, f"no slot dir matching {stem!r} under {container}"
    return matches[-1]


def test_happy_suite_container_and_slot_outputs(fixtures_dir, core_config, isolated_cwd) -> None:
    suite = fixtures_dir / "suites" / "happy.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 0)
    container = latest_suite_container(isolated_cwd)
    assert container.name.endswith("-pass")
    assert (container / "summary.txt").is_file()
    slots = list_slot_dirs(container)
    assert len(slots) == 3
    test_slot = _slot_with_stem(container, "pass_test")
    assert test_slot.name.endswith("-pass")
    assert (test_slot / "execution.sqlite").is_file()
    assert (test_slot / "summary.txt").is_file()
    phases = {
        row[0]
        for row in query_db(test_slot, "SELECT message FROM events WHERE message LIKE 'phase_enter:%'")
    }
    assert "phase_enter:test" in phases
    summary = _container_summary(container)
    assert summary["overall_result"] == "PASS"
    assert len(summary["test_slots"]) == 1


def test_setup_failure_does_not_skip_tests_without_rip_cord(
    fixtures_dir, core_config, isolated_cwd
) -> None:
    suite = fixtures_dir / "suites" / "setup_fail.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 0)
    container = latest_suite_container(isolated_cwd)
    assert _slot_with_stem(container, "setup_fail")
    assert _slot_with_stem(container, "pass_test").name.endswith("-pass")
    assert _slot_with_stem(container, "teardown_ok")
    summary = (container / "summary.txt").read_text(encoding="utf-8")
    assert "Overall result: PASS" in summary


def test_teardown_failure_does_not_fail_suite_when_tests_pass(
    fixtures_dir, core_config, isolated_cwd
) -> None:
    suite = fixtures_dir / "suites" / "teardown_fail.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 0)
    container = latest_suite_container(isolated_cwd)
    assert container.name.endswith("-pass")
    assert _slot_with_stem(container, "teardown_fail")


def test_test_script_exception_fails_suite_without_verification(
    fixtures_dir, core_config, isolated_cwd
) -> None:
    suite = fixtures_dir / "suites" / "test_script_crash.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 1)
    container = latest_suite_container(isolated_cwd)
    assert container.name.endswith("-fail")
    test_slot = _slot_with_stem(container, "crash_test")
    errors = query_db(test_slot, "SELECT message FROM events WHERE message LIKE 'script_fail:%'")
    assert errors
    assert "Overall result: FAIL" in (container / "summary.txt").read_text(encoding="utf-8")


def test_default_continues_after_test_crash(fixtures_dir, core_config, isolated_cwd) -> None:
    suite = fixtures_dir / "suites" / "multi_test_continue.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 1)
    container = latest_suite_container(isolated_cwd)
    assert len(slot_dirs_matching(container, "crash_test")) == 1
    assert len(slot_dirs_matching(container, "pass_test")) == 1
    assert _slot_with_stem(container, "teardown_ok")
    summary = _container_summary(container)
    assert len(summary["test_slots"]) == 2


def test_fail_fast_stops_after_test_crash(fixtures_dir, core_config, isolated_cwd) -> None:
    suite = fixtures_dir / "suites" / "multi_test_fail_fast_crash.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 1)
    container = latest_suite_container(isolated_cwd)
    assert len(slot_dirs_matching(container, "crash_test")) == 1
    assert slot_dirs_matching(container, "pass_test") == []
    crash_slot = _slot_with_stem(container, "crash_test")
    meta = dict(query_db(crash_slot, "SELECT key, value FROM run_metadata"))
    assert meta.get("fail_fast_stopped") == "1"


def test_fail_fast_stops_after_required_verification_fail(
    fixtures_dir, core_config, isolated_cwd
) -> None:
    suite = fixtures_dir / "suites" / "multi_test_fail_fast_verify.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 1)
    container = latest_suite_container(isolated_cwd)
    assert len(slot_dirs_matching(container, "fail_required_verify")) == 1
    assert slot_dirs_matching(container, "pass_test") == []
    fail_slot = _slot_with_stem(container, "fail_required_verify")
    meta = dict(query_db(fail_slot, "SELECT key, value FROM run_metadata"))
    assert meta.get("fail_fast_stopped") == "1"


def test_between_tests_runs_between_executions_not_before_or_after(
    fixtures_dir, core_config, isolated_cwd
) -> None:
    suite = fixtures_dir / "suites" / "between_two_tests.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 0)
    container = latest_suite_container(isolated_cwd)
    assert _slot_with_stem(container, "count_label_a")
    assert _slot_with_stem(container, "count_between")
    assert _slot_with_stem(container, "count_label_b")
    between_slot = _slot_with_stem(container, "count_between")
    phases = {
        row[0]
        for row in query_db(between_slot, "SELECT message FROM events WHERE message LIKE 'phase_enter:%'")
    }
    assert "phase_enter:between_tests" in phases


def test_repeat_count_runs_between_iterations(fixtures_dir, core_config, isolated_cwd) -> None:
    suite = fixtures_dir / "suites" / "repeat_count.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 0)
    container = latest_suite_container(isolated_cwd)
    assert len(slot_dirs_matching(container, "count_repeat")) == 3
    assert len(slot_dirs_matching(container, "count_between")) == 2


def test_repeat_for_runs_until_deadline(fixtures_dir, core_config, isolated_cwd) -> None:
    suite = fixtures_dir / "suites" / "repeat_for.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 0)
    container = latest_suite_container(isolated_cwd)
    assert len(slot_dirs_matching(container, "count_repeat")) >= 2


def test_repeat_failure_continues_when_fail_fast_false(
    fixtures_dir, core_config, isolated_cwd
) -> None:
    suite = fixtures_dir / "suites" / "repeat_fail_continue.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 1)
    container = latest_suite_container(isolated_cwd)
    assert len(slot_dirs_matching(container, "repeat_fail_first")) == 3


def test_repeat_failure_stops_when_fail_fast_true(fixtures_dir, core_config, isolated_cwd) -> None:
    suite = fixtures_dir / "suites" / "repeat_fail_fast.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 1)
    container = latest_suite_container(isolated_cwd)
    assert len(slot_dirs_matching(container, "repeat_fail_first")) == 1


def test_between_tests_crash_continues_when_fail_fast_false(
    fixtures_dir, core_config, isolated_cwd
) -> None:
    suite = fixtures_dir / "suites" / "between_crash_continue.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 0)
    container = latest_suite_container(isolated_cwd)
    assert len(slot_dirs_matching(container, "pass_test")) == 2
    assert _slot_with_stem(container, "crash_test")


def test_rip_cord_aborts_on_setup_failure(fixtures_dir, core_config, isolated_cwd) -> None:
    suite = fixtures_dir / "suites" / "setup_fail_rip_cord.toml"
    _run_suite_expect_exit(suite, core_config, isolated_cwd, 1)
    container = latest_suite_container(isolated_cwd)
    assert container.name.endswith("-fail")
    assert _slot_with_stem(container, "setup_fail")
    assert slot_dirs_matching(container, "pass_test") == []
    summary = _container_summary(container)
    assert summary["rip_cord_triggered"] is True
