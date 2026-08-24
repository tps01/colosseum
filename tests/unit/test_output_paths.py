"""U-OUT-01: output directory naming."""

from __future__ import annotations

import re

from colosseum.output.paths import (
    allocate_run_directory,
    rename_run_directory_for_result,
    sanitize_logical_name,
)


def test_sanitize_strips_unsafe_characters() -> None:
    assert sanitize_logical_name("my test!") == "my_test"
    assert sanitize_logical_name("") == "run"


def test_allocate_run_directory_format_and_collision(isolated_cwd) -> None:
    first = allocate_run_directory(isolated_cwd, "smoke test")
    first.mkdir()
    second = allocate_run_directory(isolated_cwd, "smoke test")
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_smoke_test(_\d+)?$")
    assert pattern.match(first.name)
    assert second != first
    assert second.name.endswith("_1") or first.name != second.name


def test_allocate_run_directory_under_parent(isolated_cwd) -> None:
    parent = isolated_cwd / "outputs" / "suite_container"
    parent.mkdir(parents=True)
    child = allocate_run_directory(isolated_cwd, "probe", parent=parent)
    assert child.parent == parent
    assert child.name.startswith("20")
    assert child.name.endswith("_probe")


def test_rename_run_directory_for_result_appends_status(isolated_cwd) -> None:
    run_dir = isolated_cwd / "outputs" / "2026-01-01_120000_smoke"
    run_dir.mkdir(parents=True)
    final_dir = rename_run_directory_for_result(run_dir, "FAIL")
    assert final_dir.name == "2026-01-01_120000_smoke-fail"
    assert final_dir.is_dir()
    assert not run_dir.exists()


def test_rename_run_directory_for_result_avoids_collision(isolated_cwd) -> None:
    run_dir = isolated_cwd / "outputs" / "2026-01-01_120000_smoke"
    existing = isolated_cwd / "outputs" / "2026-01-01_120000_smoke-pass"
    run_dir.mkdir(parents=True)
    existing.mkdir()
    final_dir = rename_run_directory_for_result(run_dir, "PASS")
    assert final_dir.name == "2026-01-01_120000_smoke-pass_1"
    assert final_dir.is_dir()
