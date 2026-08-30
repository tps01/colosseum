from __future__ import annotations

from colosseum.gui._browser import (
    format_summary_text,
    load_run_browser_snapshot,
    load_run_snapshot,
)


def test_load_run_browser_snapshot_reads_statuses(isolated_cwd) -> None:
    pass_run = isolated_cwd / "outputs" / "2026-01-01_120000_pass-pass"
    incomplete_run = isolated_cwd / "playground" / "outputs" / "2026-01-01_120001_incomplete"
    pass_run.mkdir(parents=True)
    incomplete_run.mkdir(parents=True)
    (pass_run / "summary.json").write_text('{"overall_result": "PASS"}', encoding="utf-8")

    snapshot = load_run_browser_snapshot(isolated_cwd)

    statuses = {row.entry.path.name: row.status for row in snapshot.rows}
    assert statuses[pass_run.name] == "PASS"
    assert statuses[incomplete_run.name] == "incomplete"
    assert snapshot.output_dirs == {pass_run.parent, incomplete_run.parent}


def test_load_run_snapshot_reads_debug_log(isolated_cwd) -> None:
    run_dir = isolated_cwd / "outputs" / "2026-01-01_120000_pass-pass"
    run_dir.mkdir(parents=True)
    (run_dir / "debug.log").write_text("hello\nworld\n", encoding="utf-8")
    (run_dir / "summary.json").write_text('{"overall_result": "PASS", "exit_code": 0}', encoding="utf-8")

    snapshot = load_run_snapshot(run_dir)

    assert snapshot.log_error is None
    assert snapshot.log_text == "hello\nworld\n"
    assert snapshot.summary is not None
    assert snapshot.summary["overall_result"] == "PASS"


def test_load_run_snapshot_missing_log(isolated_cwd) -> None:
    run_dir = isolated_cwd / "outputs" / "2026-01-01_120000_pass-pass"
    run_dir.mkdir(parents=True)

    snapshot = load_run_snapshot(run_dir)

    assert snapshot.log_text is None
    assert snapshot.log_error is not None
    assert "No debug.log" in snapshot.log_error


def test_format_summary_text_includes_failed_verifications() -> None:
    text = format_summary_text(
        {
            "overall_result": "FAIL",
            "exit_code": 1,
            "verification_counts": {"required": {"FAIL": 1}, "optional": {}},
            "failed_required_verifications": [
                {
                    "status": "FAIL",
                    "domain": "core",
                    "command": "verify",
                    "key": "voltage",
                    "message": "out of range",
                },
            ],
        },
    )

    assert "Overall: FAIL" in text
    assert "Failed required verifications:" in text
    assert "core.verify key=voltage" in text
