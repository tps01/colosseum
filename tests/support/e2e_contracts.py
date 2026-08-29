"""Black-box artifact contracts for subprocess e2e tests."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from tests.support.helpers import query_db

_WATS_NAME_RE = re.compile(r"^wats_\d{8}T\d{6}_.+\.json$")


def run_cli(
    script: Path,
    config: Path,
    cwd: Path,
    env: dict[str, str],
    *,
    extra_args: list[str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run ``colosseum run`` via subprocess."""
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
        timeout=timeout,
    )


def run_suite_cli(
    suite: Path,
    config: Path,
    cwd: Path,
    env: dict[str, str],
    *,
    extra_args: list[str] | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    """Run ``colosseum run-suite`` via subprocess."""
    cmd = [
        sys.executable,
        "-m",
        "colosseum.runner.cli",
        "run-suite",
        str(suite),
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
        timeout=timeout,
    )


def run_python_script(
    script: Path,
    cwd: Path,
    env: dict[str, str],
    *,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def read_summary_json(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "summary.json"
    assert path.is_file(), f"missing summary.json in {run_dir}"
    return json.loads(path.read_text(encoding="utf-8"))


def find_wats_json(run_dir: Path) -> Path:
    matches = sorted(run_dir.glob("wats_*.json"))
    assert matches, f"no wats_*.json in {run_dir}"
    assert len(matches) == 1, f"expected one WATS file, found {matches}"
    return matches[0]


def load_wats_json(run_dir: Path) -> dict[str, Any]:
    return json.loads(find_wats_json(run_dir).read_text(encoding="utf-8"))


def run_metadata(run_dir: Path) -> dict[str, str]:
    rows = query_db(run_dir, "SELECT key, value FROM run_metadata")
    return {str(key): str(value) for key, value in rows}


def verification_row(run_dir: Path, key: str) -> tuple[Any, ...] | None:
    rows = query_db(
        run_dir,
        "SELECT status, optional, domain FROM verifications WHERE key=? ORDER BY id DESC LIMIT 1",
        (key,),
    )
    return rows[0] if rows else None


def assert_run_artifacts(
    run_dir: Path,
    *,
    expect_pass: bool,
    expect_wats: bool = True,
) -> None:
    suffix = "-pass" if expect_pass else "-fail"
    assert run_dir.name.endswith(suffix), f"expected {suffix} suffix on {run_dir.name}"
    assert (run_dir / "debug.log").is_file()
    assert (run_dir / "execution.sqlite").is_file()
    assert (run_dir / "summary.txt").is_file()
    assert (run_dir / "summary.json").is_file()
    if expect_wats:
        wats = find_wats_json(run_dir)
        assert _WATS_NAME_RE.match(wats.name), wats.name
    meta = run_metadata(run_dir)
    assert meta.get("overall_status") == ("PASS" if expect_pass else "FAIL")
    assert meta.get("exit_code") == ("0" if expect_pass else "1")
    summary = read_summary_json(run_dir)
    assert summary["overall_result"] == ("PASS" if expect_pass else "FAIL")
    assert summary["exit_code"] == (0 if expect_pass else 1)


def assert_suite_container(container: Path, *, expect_pass: bool) -> None:
    suffix = "-pass" if expect_pass else "-fail"
    assert container.name.endswith(suffix), container.name
    assert (container / "summary.txt").is_file()
    assert (container / "summary.json").is_file()
    summary = read_summary_json(container)
    assert summary["overall_result"] == ("PASS" if expect_pass else "FAIL")
    assert "test_slots" in summary


def assert_test_slot_full_artifacts(slot_dir: Path) -> None:
    assert (slot_dir / "debug.log").is_file()
    assert (slot_dir / "execution.sqlite").is_file()
    assert (slot_dir / "summary.txt").is_file()
    assert (slot_dir / "summary.json").is_file()
    find_wats_json(slot_dir)


def assert_supporting_slot_artifacts(slot_dir: Path) -> None:
    assert (slot_dir / "debug.log").is_file()
    assert (slot_dir / "execution.sqlite").is_file()
    assert not (slot_dir / "summary.txt").exists()
    assert not (slot_dir / "summary.json").exists()
    assert list(slot_dir.glob("wats_*.json")) == []


def assert_wats_identity_fields(payload: dict[str, Any], metadata: dict[str, str]) -> None:
    assert payload.get("pn") == metadata.get("uut")
    assert payload.get("rev") == metadata.get("revision")
    assert payload.get("sn") == metadata.get("serial_number")
    assert payload.get("processCode") == metadata.get("process_code")
    assert payload.get("location") == metadata.get("location")
    assert payload.get("purpose") == metadata.get("test_intent")
