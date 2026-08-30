"""E2E-SUITE: colosseum run-suite via subprocess."""

from __future__ import annotations

import pytest

from tests.support.e2e_specifications import (
    assert_suite_container,
    assert_supporting_slot_artifacts,
    assert_test_slot_full_artifacts,
    assert_wats_identity_fields,
    load_wats_json,
    read_summary_json,
    run_suite_cli,
)
from tests.support.helpers import latest_suite_container, query_db, slot_dirs_matching, REPO_ROOT as REPO

METADATA = REPO / "tests" / "fixtures" / "metadata_example.yaml"


def _suite(fixtures_dir, name: str):
    return fixtures_dir / "suites" / name


def _slot(container, stem: str):
    matches = slot_dirs_matching(container, stem)
    assert matches, f"no slot matching {stem!r}"
    return matches[-1]


@pytest.mark.requirement("E2E-SUITE-01")
def test_happy_suite_container_passes(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    """Happy suite runs setup, test, and teardown slots; container passes."""
    proc = run_suite_cli(_suite(fixtures_dir, "happy.toml"), core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert_suite_container(container, expect_pass=True)
    assert "Overall result: PASS" in (container / "summary.txt").read_text(encoding="utf-8")
    assert (_slot(container, "pass_test") / "execution.sqlite").is_file()


@pytest.mark.requirement("E2E-SUITE-02")
def test_slot_artifact_sets(core_config, fixtures_dir, isolated_cwd, subprocess_env) -> None:
    """Test slots get full artifacts; supporting slots get log and sqlite only."""
    proc = run_suite_cli(_suite(fixtures_dir, "happy.toml"), core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert_test_slot_full_artifacts(_slot(container, "pass_test"))
    assert_supporting_slot_artifacts(_slot(container, "setup_ok"))
    assert_supporting_slot_artifacts(_slot(container, "teardown_ok"))


@pytest.mark.requirement("E2E-SUITE-03")
def test_setup_fail_exits_zero_without_rip_cord(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    """Setup failure does not fail the suite when rip_cord is false."""
    proc = run_suite_cli(_suite(fixtures_dir, "setup_fail.toml"), core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert _slot(container, "pass_test").name.endswith("-pass")


@pytest.mark.requirement("E2E-SUITE-04")
def test_teardown_fail_does_not_fail_suite(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    """Teardown failure does not fail the suite when tests pass."""
    proc = run_suite_cli(
        _suite(fixtures_dir, "teardown_fail.toml"), core_config, isolated_cwd, subprocess_env
    )
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert_suite_container(container, expect_pass=True)


@pytest.mark.requirement("E2E-SUITE-05")
def test_test_script_crash_fails_suite(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    """Test script crash fails the suite."""
    proc = run_suite_cli(
        _suite(fixtures_dir, "test_script_crash.toml"), core_config, isolated_cwd, subprocess_env
    )
    assert proc.returncode == 1, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert_suite_container(container, expect_pass=False)
    test_slot = _slot(container, "crash_test")
    errors = query_db(test_slot, "SELECT message FROM events WHERE message LIKE 'script_fail:%'")
    assert errors


@pytest.mark.requirement("E2E-SUITE-06")
def test_fail_fast_stops_remaining_tests(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    """fail_fast=true skips remaining tests after a test-slot failure."""
    proc = run_suite_cli(
        _suite(fixtures_dir, "multi_test_fail_fast_crash.toml"),
        core_config,
        isolated_cwd,
        subprocess_env,
    )
    assert proc.returncode == 1, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert slot_dirs_matching(container, "crash_test")
    assert slot_dirs_matching(container, "pass_test") == []
    crash_slot = _slot(container, "crash_test")
    meta = dict(query_db(crash_slot, "SELECT key, value FROM run_metadata"))
    assert meta.get("fail_fast_stopped") == "1"


@pytest.mark.requirement("E2E-SUITE-07")
def test_rip_cord_aborts_on_setup_failure(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    """rip_cord=true aborts on setup failure, runs teardown, fails suite."""
    proc = run_suite_cli(
        _suite(fixtures_dir, "setup_fail_rip_cord.toml"), core_config, isolated_cwd, subprocess_env
    )
    assert proc.returncode == 1, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert_suite_container(container, expect_pass=False)
    assert _slot(container, "setup_fail")
    assert slot_dirs_matching(container, "pass_test") == []
    summary = read_summary_json(container)
    assert summary["rip_cord_triggered"] is True


@pytest.mark.requirement("E2E-SUITE-08")
def test_between_tests_runs_between_executions(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    """between_tests runs between test slots, not before the first or after the last."""
    proc = run_suite_cli(
        _suite(fixtures_dir, "between_two_tests.toml"), core_config, isolated_cwd, subprocess_env
    )
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert _slot(container, "count_label_a")
    assert _slot(container, "count_between")
    assert _slot(container, "count_label_b")


@pytest.mark.requirement("E2E-SUITE-09")
def test_repeat_count_runs_between_iterations(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    """repeat_count runs N iterations; between_tests runs between iterations."""
    proc = run_suite_cli(_suite(fixtures_dir, "repeat_count.toml"), core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert len(slot_dirs_matching(container, "count_repeat")) == 3
    assert len(slot_dirs_matching(container, "count_between")) == 2


@pytest.mark.requirement("E2E-SUITE-10")
def test_suite_metadata_propagates_to_wats(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    """Suite --metadata propagates identity fields to test-slot WATS files."""
    proc = run_suite_cli(
        _suite(fixtures_dir, "smoke.toml"),
        core_config,
        isolated_cwd,
        subprocess_env,
        extra_args=["--metadata", str(METADATA)],
    )
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    test_slot = _slot(container, "optional_fail_test")
    payload = load_wats_json(test_slot)
    assert_wats_identity_fields(
        payload,
        {
            "uut": "PARTNUMBER",
            "revision": "1.2.3",
            "serial_number": "123",
            "process_code": "1234",
            "location": "TBD_PHYSICAL_LOCATION",
            "test_intent": "Acceptance",
        },
    )


@pytest.mark.requirement("E2E-CFG-01")
def test_bad_config_exits_one(fixtures_dir, isolated_cwd, subprocess_env) -> None:
    """Invalid config TOML exits 1 before the suite runs."""
    config = isolated_cwd / "bad.toml"
    config.write_text('[runtime\nlabel = "broken"\n', encoding="utf-8")
    proc = run_suite_cli(_suite(fixtures_dir, "happy.toml"), config, isolated_cwd, subprocess_env)
    assert proc.returncode == 1
    assert not (isolated_cwd / "outputs").exists()


@pytest.mark.requirement("E2E-SUITE-11")
def test_suite_procedure_mode_skips_verifications(
    core_config, fixtures_dir, isolated_cwd, subprocess_env,
) -> None:
    """Suite -p runs test slots in procedure mode without verification rows."""
    proc = run_suite_cli(
        _suite(fixtures_dir, "procedure_suite.toml"),
        core_config,
        isolated_cwd,
        subprocess_env,
        extra_args=["-p"],
    )
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    slot = _slot(container, "optional_fail_test")
    assert query_db(slot, "SELECT COUNT(*) FROM verifications")[0][0] == 0
    assert query_db(slot, "SELECT COUNT(*) FROM measurements")[0][0] >= 1
