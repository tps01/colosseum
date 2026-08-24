"""I-RUN: endex, artifacts, read API."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

import colosseum as col
from colosseum.config import load_config

from tests.support.core_api import measure_value, verify_value
from tests.support.helpers import latest_output_dir, query_db, run_endex_expect_code


def test_decorators_create_sqlite_log_and_summary(core_config, isolated_cwd) -> None:
    load_config(core_config)
    measure_value(key="v1", value=3.3)
    active_dir = col.context.get_context().output_dir
    assert active_dir is not None
    assert not active_dir.name.endswith("-pass")
    assert not active_dir.name.endswith("-fail")
    run_endex_expect_code(0)
    run_dir = latest_output_dir(isolated_cwd)
    assert run_dir.name.endswith("-pass")
    assert not active_dir.exists()
    assert col.context.get_context().output_dir == run_dir
    assert (run_dir / "debug.log").is_file()
    assert (run_dir / "execution.sqlite").is_file()
    tables = {
        row[0]
        for row in query_db(run_dir, "SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"run_metadata", "measurements", "verifications", "events", "artifacts"} <= tables
    summary = (run_dir / "summary.txt").read_text(encoding="utf-8")
    assert "Overall result: PASS" in summary
    import json

    payload = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert payload["overall_result"] == "PASS"
    assert payload["exit_code"] == 0
    assert payload["output_directory"] == str(run_dir)


def test_read_api_returns_measurement_keys(core_config, isolated_cwd) -> None:
    load_config(core_config)
    measure_value(key="read_key", value=3.3)
    keys = {m.key for m in col.database.read_measurements()}
    assert "read_key" in keys
    run_endex_expect_code(0)


def test_missing_measurement_yields_exit_one(core_config, isolated_cwd) -> None:
    load_config(core_config)
    verify_value(key="missing_rail", expected_val=1.0, tolerance=0.1)
    run_endex_expect_code(1)
    run_dir = latest_output_dir(isolated_cwd)
    assert run_dir.name.endswith("-fail")
    status = query_db(
        run_dir,
        "SELECT status FROM verifications WHERE key=?",
        ("missing_rail",),
    )
    assert status and status[0][0] == "ERROR"


def test_endex_second_call_reuses_final_exit_code(core_config, isolated_cwd) -> None:
    load_config(core_config)
    verify_value(key="missing_rail", expected_val=1.0, tolerance=0.1)
    run_endex_expect_code(1)
    with pytest.raises(SystemExit) as exc:
        col.endex()
    assert exc.value.code == 1


def test_required_command_error_endex_fails(core_config, isolated_cwd) -> None:
    from colosseum.decorators import command

    @command
    def _boom(*, key: str = "") -> None:
        raise RuntimeError("command procedural failure")

    load_config(core_config)
    with pytest.raises(RuntimeError, match="command procedural failure"):
        _boom(key="step")
    run_endex_expect_code(1)
    run_dir = latest_output_dir(isolated_cwd)
    assert run_dir.name.endswith("-fail")
    rows = query_db(
        run_dir,
        "SELECT status, message FROM commands WHERE command=?",
        ("_boom",),
    )
    assert rows and rows[0][0] == "ERROR"
    assert "command procedural failure" in rows[0][1]


def test_optional_fail_still_exits_zero(core_config, isolated_cwd) -> None:
    load_config(core_config)
    measure_value(key="vrail_3v3", value=3.3)
    verify_value(key="vrail_3v3", expected_val=3.3, tolerance=0.1)
    measure_value(key="probe_optional", value=2.2)
    verify_value(key="probe_optional", expected_val=1.8, tolerance=0.1, optional=True)
    run_endex_expect_code(0)
    run_dir = latest_output_dir(isolated_cwd)
    row = col.context.get_context()
    # context finalized; query sqlite directly
    import sqlite3

    conn = sqlite3.connect(run_dir / "execution.sqlite")
    opt = conn.execute(
        "SELECT status FROM verifications WHERE key=? AND optional=1",
        ("probe_optional",),
    ).fetchone()
    conn.close()
    assert opt is not None and opt[0] == "FAIL"


def test_direct_script_unhandled_exception_auto_finalizes_fail(
    core_config,
    isolated_cwd,
    subprocess_env,
) -> None:
    script = isolated_cwd / "direct_crash.py"
    script.write_text(
        "\n".join(
            [
                "import colosseum as col",
                f"col.config.load_config({str(core_config)!r})",
                "raise RuntimeError('direct boom')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=isolated_cwd,
        env=subprocess_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert proc.returncode != 0
    run_dir = latest_output_dir(isolated_cwd)
    assert run_dir.name.endswith("-fail")
    unfinalized = [
        path
        for path in (isolated_cwd / "outputs").glob("*_direct_crash")
        if path.is_dir()
    ]
    assert unfinalized == []
    payload = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert payload["overall_result"] == "FAIL"
    assert payload["suite_error"] is True
    assert "unhandled exception" in payload["failed_required_outcomes"][0]["message"]
