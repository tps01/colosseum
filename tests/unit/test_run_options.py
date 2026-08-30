"""Unit tests for CLI run option helpers."""

from __future__ import annotations

from pathlib import Path

from colosseum.runner.run_options import RunOptions, resolve_input_path, resolve_outputs_root


def test_resolve_input_path_with_base(tmp_path) -> None:
    base = tmp_path / "cases"
    script = base / "pass_test.py"
    script.parent.mkdir()
    script.write_text("x", encoding="utf-8")
    resolved = resolve_input_path(base, "pass_test.py")
    assert resolved == script.resolve()


def test_resolve_input_path_without_base(tmp_path) -> None:
    script = tmp_path / "pass_test.py"
    script.write_text("x", encoding="utf-8")
    resolved = resolve_input_path(None, str(script))
    assert resolved == script.resolve()


def test_resolve_outputs_root_default(isolated_cwd) -> None:
    root = resolve_outputs_root(RunOptions())
    assert root == isolated_cwd / "outputs"


def test_resolve_outputs_root_override(tmp_path) -> None:
    custom = tmp_path / "bench_runs"
    root = resolve_outputs_root(RunOptions(outputs_root=custom))
    assert root == custom
