"""E2E-RUN: colosseum run via subprocess."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.e2e_contracts import (
    assert_run_artifacts,
    assert_wats_identity_fields,
    find_wats_json,
    load_wats_json,
    run_cli,
    run_metadata,
    verification_row,
)
from tests.support.helpers import latest_output_dir, query_db, REPO_ROOT as REPO

OPTIONAL_FAIL = REPO / "tests" / "fixtures" / "scripts" / "optional_fail_test.py"
FAIL_REQUIRED = REPO / "tests" / "fixtures" / "scripts" / "fail_required_verify.py"
CRASH = REPO / "tests" / "fixtures" / "scripts" / "crash_test.py"
COMMAND_ERROR = REPO / "tests" / "fixtures" / "scripts" / "command_error_test.py"
WATS_SMOKE = REPO / "tests" / "fixtures" / "scripts" / "wats_smoke_test.py"
ACTIVE_DIR_PROBE = REPO / "tests" / "fixtures" / "scripts" / "active_dir_probe.py"
METADATA = REPO / "tests" / "fixtures" / "metadata_example.yaml"


@pytest.mark.requirement("E2E-RUN-01")
def test_pass_run_writes_full_artifacts(core_config, isolated_cwd, subprocess_env) -> None:
    """A passing test run writes the full artifact set and exits 0."""
    proc = run_cli(OPTIONAL_FAIL, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    assert "Colosseum version:" in proc.stdout
    assert "Overall result: PASS" in proc.stdout
    run_dir = latest_output_dir(isolated_cwd)
    assert_run_artifacts(run_dir, expect_pass=True)


@pytest.mark.requirement("E2E-RUN-02")
def test_optional_verification_fail_exits_zero(core_config, isolated_cwd, subprocess_env) -> None:
    """Optional verification FAIL does not change the exit code."""
    proc = run_cli(OPTIONAL_FAIL, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    opt = verification_row(run_dir, "optional")
    assert opt is not None and opt[0] == "FAIL" and opt[1] == 1
    req = verification_row(run_dir, "required")
    assert req is not None and req[0] == "PASS"


@pytest.mark.requirement("E2E-RUN-03")
def test_missing_measurement_exits_one(core_config, isolated_cwd, subprocess_env) -> None:
    """Required verification ERROR (missing measurement) exits 1."""
    proc = run_cli(FAIL_REQUIRED, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 1, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    assert_run_artifacts(run_dir, expect_pass=False)
    row = verification_row(run_dir, "missing")
    assert row is not None and row[0] == "ERROR"


@pytest.mark.requirement("E2E-RUN-04")
def test_script_crash_exits_one_and_finalizes(core_config, isolated_cwd, subprocess_env) -> None:
    """Uncaught script exception exits 1; artifacts are still finalized."""
    proc = run_cli(CRASH, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 1
    run_dir = latest_output_dir(isolated_cwd)
    assert (run_dir / "debug.log").is_file()
    assert (run_dir / "execution.sqlite").is_file()
    assert (run_dir / "summary.txt").is_file()
    assert (run_dir / "summary.json").is_file()
    assert run_metadata(run_dir).get("overall_status") == "FAIL"


@pytest.mark.requirement("E2E-RUN-05")
def test_command_error_records_row_and_fails(core_config, isolated_cwd, subprocess_env) -> None:
    """Required @command ERROR exits 1; command row is recorded."""
    proc = run_cli(COMMAND_ERROR, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 1, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    assert run_metadata(run_dir).get("overall_status") == "FAIL"
    rows = query_db(
        run_dir,
        "SELECT status, message, optional FROM commands WHERE command=?",
        ("_boom",),
    )
    assert rows
    assert rows[0][0] == "ERROR"
    assert "command procedural failure" in rows[0][1]
    assert rows[0][2] in (0, False)


@pytest.mark.requirement("E2E-RUN-06")
def test_no_artifacts_skips_output_dir(core_config, isolated_cwd, subprocess_env) -> None:
    """--no-artifacts skips persisted output."""
    proc = run_cli(
        OPTIONAL_FAIL,
        core_config,
        isolated_cwd,
        subprocess_env,
        extra_args=["--no-artifacts"],
    )
    assert proc.returncode == 0, proc.stderr
    assert "no-artifacts mode" in proc.stdout
    assert not (isolated_cwd / "outputs").exists()


@pytest.mark.requirement("E2E-RUN-07")
def test_metadata_enriches_wats_report(core_config, isolated_cwd, subprocess_env) -> None:
    """--metadata enriches the WATS report with YAML identity fields."""
    proc = run_cli(
        WATS_SMOKE,
        core_config,
        isolated_cwd,
        subprocess_env,
        extra_args=["--metadata", str(METADATA)],
    )
    assert proc.returncode == 0, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    payload = load_wats_json(run_dir)
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


@pytest.mark.requirement("E2E-RUN-08")
def test_output_dir_renamed_after_finalize(core_config, isolated_cwd, subprocess_env) -> None:
    """During execution the output directory has no suffix; after finalize it is renamed."""
    proc = run_cli(ACTIVE_DIR_PROBE, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    active_name = (isolated_cwd / "active_dir_probe.txt").read_text(encoding="utf-8")
    assert not active_name.endswith("-pass")
    assert not active_name.endswith("-fail")
    run_dir = latest_output_dir(isolated_cwd)
    assert run_dir.name == f"{active_name}-pass"
