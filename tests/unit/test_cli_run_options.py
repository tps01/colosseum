"""CLI parser coverage for expanded run flags."""

from __future__ import annotations

import pytest

from colosseum.runner.cli import _build_parser


def test_run_parser_accepts_shared_and_run_only_flags() -> None:
    args = _build_parser().parse_args(
        [
            "run",
            "pass_test.py",
            "-i",
            "./tests",
            "-o",
            "./runs",
            "-g",
            "config.toml",
            "-m",
            "meta.yaml",
            "-c",
            "stub.ping,key=dev1",
            "-p",
            "--show-faults",
        ],
    )
    assert args.command == "run"
    assert args.test_file == "pass_test.py"
    assert args.input_dir.name == "tests"
    assert args.output_dir.name == "runs"
    assert args.config_path == "config.toml"
    assert args.metadata_path == "meta.yaml"
    assert args.plugin_commands == ["stub.ping,key=dev1"]
    assert args.procedure is True
    assert args.show_faults is True


def test_run_parser_allows_command_without_test_file() -> None:
    args = _build_parser().parse_args(["run", "-c", "stub.ping", "-g", "config.toml"])
    assert args.test_file is None
    assert args.plugin_commands == ["stub.ping"]


def test_run_parser_rejects_procedure_and_previous_output_together() -> None:
    with pytest.raises(SystemExit):
        _build_parser().parse_args(
            ["run", "pass_test.py", "-p", "-u", "./prior", "-g", "config.toml"],
        )


def test_suite_parser_has_shared_flags_and_procedure_only() -> None:
    args = _build_parser().parse_args(
        ["run-suite", "suite.toml", "-i", "./suites", "-o", "./runs", "-g", "config.toml", "-p"],
    )
    assert args.command == "run-suite"
    assert args.procedure is True
    assert not hasattr(args, "plugin_commands") or args.plugin_commands in ([], None)
