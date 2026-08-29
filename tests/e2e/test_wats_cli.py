"""E2E-ART-WATS: WATS JSON export via subprocess."""

from __future__ import annotations

import re

import pytest

from tests.support.e2e_contracts import (
    assert_wats_identity_fields,
    find_wats_json,
    load_wats_json,
    run_cli,
)
from tests.support.helpers import latest_output_dir, REPO_ROOT as REPO

OPTIONAL_FAIL = REPO / "tests" / "fixtures" / "scripts" / "optional_fail_test.py"
WATS_SMOKE = REPO / "tests" / "fixtures" / "scripts" / "wats_smoke_test.py"
WATS_BEST_EFFORT = REPO / "tests" / "fixtures" / "scripts" / "wats_best_effort_test.py"
METADATA = REPO / "tests" / "fixtures" / "metadata_example.yaml"

_WATS_NAME_RE = re.compile(r"^wats_\d{8}T\d{6}_.+\.json$")


@pytest.mark.requirement("E2E-ART-WATS-01")
def test_wats_file_always_written(core_config, isolated_cwd, subprocess_env) -> None:
    """WATS JSON is written on every normal run with artifacts enabled."""
    proc = run_cli(OPTIONAL_FAIL, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    assert find_wats_json(run_dir).is_file()


@pytest.mark.requirement("E2E-ART-WATS-02")
def test_wats_filename_pattern(core_config, isolated_cwd, subprocess_env) -> None:
    """WATS filename matches wats_<UTCdatetime>_<script_stem>.json."""
    proc = run_cli(OPTIONAL_FAIL, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    wats = find_wats_json(run_dir)
    assert _WATS_NAME_RE.match(wats.name), wats.name
    assert wats.name.endswith("_optional_fail_test.json")


@pytest.mark.requirement("E2E-ART-WATS-03")
def test_wats_metadata_identity_fields(core_config, isolated_cwd, subprocess_env) -> None:
    """Metadata YAML populates WATS identity fields."""
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


@pytest.mark.requirement("E2E-ART-WATS-04")
def test_wats_best_effort_without_metadata(core_config, isolated_cwd, subprocess_env) -> None:
    """Without metadata, best-effort WATS export still succeeds."""
    proc = run_cli(WATS_BEST_EFFORT, core_config, isolated_cwd, subprocess_env)
    assert proc.returncode == 0, proc.stderr
    run_dir = latest_output_dir(isolated_cwd)
    payload = load_wats_json(run_dir)
    assert payload.get("type") == "T"
    assert "root" in payload
    assert isinstance(payload.get("pn"), str)
