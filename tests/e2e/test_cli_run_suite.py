"""E2E-W3: colosseum run-suite via subprocess."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.helpers import latest_suite_container, query_db, slot_dirs_matching

from tests.support.helpers import REPO_ROOT as REPO


def _cli_run_suite(suite: Path, config: Path, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "colosseum.runner.cli",
            "run-suite",
            str(suite),
            "--config",
            str(config),
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.requirement("E2E-W3-01")
def test_run_suite_fixture_happy(core_config, fixtures_dir, isolated_cwd, subprocess_env) -> None:
    suite = fixtures_dir / "suites" / "happy.toml"
    proc = _cli_run_suite(suite, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    summary = (container / "summary.txt").read_text(encoding="utf-8")
    assert "fixture_happy" in summary or "Overall result: PASS" in summary
    test_slot = slot_dirs_matching(container, "pass_test")[-1]
    assert (test_slot / "execution.sqlite").is_file()


@pytest.mark.requirement("E2E-W3-01")
def test_run_suite_smoke_core_api(core_config, fixtures_dir, isolated_cwd, subprocess_env) -> None:
    suite = fixtures_dir / "suites" / "smoke.toml"
    proc = _cli_run_suite(suite, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    test_slot = slot_dirs_matching(container, "optional_fail_test")[-1]
    domains = {
        row[0]
        for row in query_db(test_slot, "SELECT DISTINCT domain FROM measurements")
    }
    assert domains == {"core"}
    summary = (container / "summary.txt").read_text(encoding="utf-8")
    assert "Overall result: PASS" in summary


def test_run_suite_setup_fail_exits_zero_without_rip_cord(
    core_config, fixtures_dir, isolated_cwd, subprocess_env
) -> None:
    suite = fixtures_dir / "suites" / "setup_fail.toml"
    proc = _cli_run_suite(suite, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    container = latest_suite_container(isolated_cwd)
    assert slot_dirs_matching(container, "pass_test")


def test_run_suite_bad_config_exits_one(fixtures_dir, isolated_cwd, subprocess_env) -> None:
    config = isolated_cwd / "bad.toml"
    config.write_text(
        "[runtime\n"
        "label = \"broken\"\n",
        encoding="utf-8",
    )
    suite = fixtures_dir / "suites" / "happy.toml"
    proc = _cli_run_suite(suite, config, isolated_cwd, subprocess_env)
    assert proc.returncode == 1
