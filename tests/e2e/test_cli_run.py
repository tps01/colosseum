"""E2E-W1/W2: colosseum run via subprocess."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.helpers import latest_output_dir, query_db, verification_row

from tests.support.helpers import REPO_ROOT as REPO


def _cli_run(
    script: Path,
    config: Path,
    cwd: Path,
    env: dict[str, str],
    *,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        "-m",
        "colosseum.runner.cli",
        "run",
        str(script),
        "--config",
        str(config),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.requirement("E2E-W1-01")
def test_cli_run_no_artifacts_skips_output_dir(core_config, isolated_cwd, subprocess_env) -> None:
    script = REPO / "tests" / "fixtures" / "scripts" / "optional_fail_test.py"
    proc = _cli_run(script, core_config, isolated_cwd, subprocess_env, extra_args=["--no-artifacts"])
    assert proc.returncode == 0, proc.stderr
    assert "Colosseum version:" in proc.stdout
    assert "no-artifacts mode" in proc.stdout
    assert not (isolated_cwd / "outputs").exists()


@pytest.mark.requirement("E2E-W1-01")
def test_cli_run_records_core_evidence(core_config, isolated_cwd, subprocess_env) -> None:
    script = REPO / "tests" / "fixtures" / "scripts" / "optional_fail_test.py"
    proc = _cli_run(script, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    assert "Colosseum version:" in proc.stdout
    assert "Overall result:" in proc.stdout
    run_dir = latest_output_dir(isolated_cwd)
    opt = verification_row(run_dir, "optional")
    assert opt is not None and opt[0] == "FAIL" and opt[1] == 1
    req = verification_row(run_dir, "required")
    assert req is not None and req[0] == "PASS"


@pytest.mark.requirement("E2E-W1-03")
def test_cli_run_missing_measurement_exits_one(core_config, isolated_cwd, subprocess_env) -> None:
    script = REPO / "tests" / "fixtures" / "scripts" / "fail_required_verify.py"
    proc = _cli_run(script, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 1, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    row = verification_row(run_dir, "missing")
    assert row is not None and row[0] == "ERROR"


def test_cli_run_script_crash_exits_one_and_finalizes(core_config, isolated_cwd, subprocess_env) -> None:
    script = REPO / "tests" / "fixtures" / "scripts" / "crash_test.py"
    proc = _cli_run(script, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 1
    run_dir = latest_output_dir(isolated_cwd)
    assert (run_dir / "debug.log").is_file()
    assert (run_dir / "execution.sqlite").is_file()
    assert (run_dir / "summary.txt").is_file()
    assert (run_dir / "summary.json").is_file()
    meta = dict(query_db(run_dir, "SELECT key, value FROM run_metadata"))
    assert meta.get("overall_status") == "FAIL"
    assert meta.get("exit_code") == "1"


def test_cli_run_command_error_records_row_and_fails(
    core_config, isolated_cwd, subprocess_env
) -> None:
    script = REPO / "tests" / "fixtures" / "scripts" / "command_error_test.py"
    proc = _cli_run(script, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 1, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    meta = dict(query_db(run_dir, "SELECT key, value FROM run_metadata"))
    assert meta.get("overall_status") == "FAIL"
    assert meta.get("exit_code") == "1"
    rows = query_db(
        run_dir,
        "SELECT status, message, optional FROM commands WHERE command=?",
        ("_boom",),
    )
    assert rows, "expected ERROR command row for _boom"
    assert rows[0][0] == "ERROR"
    assert "command procedural failure" in rows[0][1]
    assert rows[0][2] in (0, False)


def test_cli_run_system_exit_marks_script_failure(core_config, isolated_cwd, subprocess_env) -> None:
    script = isolated_cwd / "sys_exit_test.py"
    script.write_text(
        "import sys\n\n"
        "def main():\n"
        "    sys.exit(2)\n",
        encoding="utf-8",
    )
    proc = _cli_run(script, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 1
    run_dir = latest_output_dir(isolated_cwd)
    meta = dict(query_db(run_dir, "SELECT key, value FROM run_metadata"))
    events = "\n".join(
        row[0]
        for row in query_db(run_dir, "SELECT message FROM events ORDER BY id")
    )
    assert meta.get("overall_status") == "FAIL"
    assert "script_exit:" in events
