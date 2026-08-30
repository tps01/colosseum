"""E2E-DIR: direct Python execution."""

from __future__ import annotations

import pytest

from tests.support.e2e_specifications import (
    assert_run_artifacts,
    run_cli,
    run_python_script,
    verification_row,
)
from tests.support.helpers import latest_output_dir, REPO_ROOT as REPO

OPTIONAL_FAIL = REPO / "tests" / "fixtures" / "scripts" / "optional_fail_test.py"
CLI_NO_ENDEX = REPO / "tests" / "fixtures" / "scripts" / "cli_no_endex_test.py"


@pytest.mark.requirement("E2E-DIR-01")
def test_direct_python_matches_cli_specification(core_config, isolated_cwd, subprocess_env) -> None:
    """python script.py with load_config and col.endex() matches the CLI artifact specification."""
    proc = run_python_script(OPTIONAL_FAIL, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    assert_run_artifacts(run_dir, expect_pass=True)
    assert verification_row(run_dir, "optional")[0] == "FAIL"
    assert verification_row(run_dir, "required")[0] == "PASS"


@pytest.mark.requirement("E2E-DIR-02")
def test_cli_finalizes_without_endex_in_script(core_config, isolated_cwd, subprocess_env) -> None:
    """CLI invokes main() only; the runner finalizes without endex() in the script."""
    proc = run_cli(CLI_NO_ENDEX, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    assert_run_artifacts(run_dir, expect_pass=True)
