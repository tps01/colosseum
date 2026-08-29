"""Unit tests for output run directory helpers."""

from __future__ import annotations

import os

from colosseum.config import load_config
from colosseum.runner.runtime import (
    find_output_directories,
    find_run_directory,
    list_run_directory_entries,
    list_run_directories,
    read_summary_json,
)

from tests.support.core_api import measure_value
from tests.support.helpers import latest_output_dir, run_endex_expect_code


def test_list_run_directories_empty_when_no_outputs(isolated_cwd) -> None:
    assert list_run_directories(isolated_cwd) == []


def test_find_output_directories_searches_only_bounded_depth(isolated_cwd) -> None:
    root_outputs = isolated_cwd / "outputs"
    one_down_outputs = isolated_cwd / "playground" / "outputs"
    two_down_outputs = isolated_cwd / "projects" / "demo" / "outputs"
    too_deep_outputs = isolated_cwd / "projects" / "demo" / "nested" / "outputs"
    for outputs_dir in [root_outputs, one_down_outputs, two_down_outputs, too_deep_outputs]:
        outputs_dir.mkdir(parents=True)

    outputs_dirs = find_output_directories(isolated_cwd, max_depth=2)

    assert outputs_dirs == [root_outputs, one_down_outputs, two_down_outputs]


def test_list_run_directory_entries_includes_nearby_output_roots(isolated_cwd) -> None:
    root_run = isolated_cwd / "outputs" / "2026-01-01_120000_root"
    nested_run = isolated_cwd / "playground" / "outputs" / "2026-01-01_120001_nested"
    root_run.mkdir(parents=True)
    nested_run.mkdir(parents=True)
    os.utime(root_run, (1_800_000_000.0, 1_800_000_000.0))
    os.utime(nested_run, (1_800_000_001.0, 1_800_000_001.0))

    entries = list_run_directory_entries(isolated_cwd)

    assert [entry.path for entry in entries] == [nested_run, root_run]
    assert [entry.outputs_dir for entry in entries] == [
        isolated_cwd / "playground" / "outputs",
        isolated_cwd / "outputs",
    ]


def test_list_and_find_after_run(core_config, isolated_cwd) -> None:
    load_config(core_config)
    measure_value(key="k1", value=3.3)
    run_endex_expect_code(0)
    run_dir = latest_output_dir(isolated_cwd)
    runs = list_run_directories(isolated_cwd)
    assert runs[0] == run_dir

    summary = read_summary_json(run_dir)
    assert summary is not None
    logical_name = summary["test_case"]
    assert find_run_directory(isolated_cwd, logical_name) == run_dir


def test_find_run_directory_respects_since(isolated_cwd) -> None:
    outputs = isolated_cwd / "outputs"
    outputs.mkdir()
    old = outputs / "2020-01-01_000000_old_run"
    old.mkdir()
    os.utime(old, (1_000_000_000.0, 1_000_000_000.0))
    since = 1_700_000_000.0
    new = outputs / "2026-01-01_120000_smoke"
    new.mkdir()
    os.utime(new, (1_800_000_000.0, 1_800_000_000.0))
    assert find_run_directory(isolated_cwd, "smoke", since=since) == new
    assert find_run_directory(isolated_cwd, "old_run", since=since) is None


def test_find_run_directory_collision_suffix(isolated_cwd) -> None:
    outputs = isolated_cwd / "outputs"
    outputs.mkdir()
    run_dir = outputs / "2026-01-01_120000_smoke_1"
    run_dir.mkdir()
    assert find_run_directory(isolated_cwd, "smoke") == run_dir


def test_find_run_directory_result_suffix(isolated_cwd) -> None:
    outputs = isolated_cwd / "outputs"
    outputs.mkdir()
    run_dir = outputs / "2026-01-01_120000_smoke-fail"
    run_dir.mkdir()
    assert find_run_directory(isolated_cwd, "smoke") == run_dir


def test_read_summary_json_missing(isolated_cwd) -> None:
    run_dir = isolated_cwd / "outputs" / "empty_run"
    run_dir.mkdir(parents=True)
    assert read_summary_json(run_dir) is None


def test_read_summary_json_round_trip(core_config, isolated_cwd) -> None:
    load_config(core_config)
    measure_value(key="k1", value=3.3)
    run_endex_expect_code(0)
    run_dir = latest_output_dir(isolated_cwd)
    payload = read_summary_json(run_dir)
    assert payload is not None
    assert payload["overall_result"] == "PASS"
    assert payload["exit_code"] == 0
