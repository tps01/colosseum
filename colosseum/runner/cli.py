from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..config import ConfigError, load_config
from ..context import init_context
from ..output import ensure_runtime_ready
from ..results import endex
from .single_test import ScriptRunError, run_script
from .suite import SuiteError, run_suite

_DESCRIPTION = (
    "Colosseum test automation: run Python test scripts and suites with bench configuration."
)
_EPILOG = """examples:
  colosseum run my_test.py --config bench.toml
  colosseum run-suite suite.toml --config bench.toml -d
  colosseum --gui
"""


def _add_common_run_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        dest="config_path",
        metavar="PATH",
        help="TOML configuration consumed by installed plugins",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Include DEBUG logs on stdout",
    )
    parser.add_argument(
        "--no-artifacts",
        action="store_true",
        help="Skip outputs/, debug.log, and on-disk execution.sqlite (utility/script mode)",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="colosseum",
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--gui", action="store_true", help="Launch the desktop GUI runner")
    sub = parser.add_subparsers(dest="command", required=False)

    run_parser = sub.add_parser(
        "run",
        help="Run a single Python test file",
        description="Initialize runtime, call the script's main(), and finalize with col.endex().",
    )
    run_parser.add_argument("test_file", help="Path to the Python test script")
    _add_common_run_options(run_parser)

    suite_parser = sub.add_parser(
        "run-suite",
        help="Run a suite TOML (setup, tests, teardown)",
        description=(
            "Run setup scripts, test scripts, and teardown scripts in one output directory."
        ),
    )
    suite_parser.add_argument("suite_file", help="Path to the suite TOML file")
    _add_common_run_options(suite_parser)

    help_parser = sub.add_parser(
        "help",
        help="Show help for colosseum or a subcommand",
        description="Print usage for colosseum or a specific subcommand.",
    )
    help_parser.add_argument(
        "topic",
        nargs="?",
        choices=("run", "run-suite"),
        help="Subcommand to describe (default: top-level usage)",
    )
    return parser


def _print_help(parser: argparse.ArgumentParser, topic: str | None = None) -> None:
    if topic is None:
        parser.print_help()
        return
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparser = action.choices.get(topic)
            if subparser is not None:
                subparser.print_help()
                return
    parser.error(f"unknown help topic: {topic}")


def _load_run_config(config_path: str | None) -> None:
    if config_path:
        load_config(config_path)


def _run_single_test(
    test_path: Path,
    config_path: str | None,
    debug: bool,
    *,
    no_artifacts: bool = False,
) -> None:
    ctx = init_context(
        test_case_name=test_path.stem,
        config_path=Path(config_path).resolve() if config_path else None,
        no_artifacts=no_artifacts,
    )
    ctx.debug_logging = debug
    _load_run_config(config_path)
    ensure_runtime_ready(ctx)
    try:
        run_script(test_path)
    except ScriptRunError:
        ctx.result_aggregator.mark_suite_error("test script failed")
    finally:
        endex()


def run_cli(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        from ..gui.app import main as gui_main

        gui_main()
        return 0

    if args.command is None:
        _print_help(parser)
        return 0

    if args.command == "help":
        _print_help(parser, getattr(args, "topic", None))
        return 0

    if args.command == "run":
        test_path = Path(args.test_file).resolve()
        if not test_path.exists():
            raise SystemExit(1)
        try:
            _run_single_test(
                test_path,
                args.config_path,
                bool(args.debug),
                no_artifacts=bool(getattr(args, "no_artifacts", False)),
            )
        except ConfigError:
            raise SystemExit(1) from None
        return 0

    if args.command == "run-suite":
        suite_path = Path(args.suite_file).resolve()
        if not suite_path.exists():
            raise SystemExit(1)
        try:
            config = Path(args.config_path).resolve() if args.config_path else None
            run_suite(
                suite_path,
                config,
                debug=bool(args.debug),
                no_artifacts=bool(getattr(args, "no_artifacts", False)),
            )
        except (ConfigError, SuiteError):
            raise SystemExit(1) from None
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1


def main(argv: list[str] | None = None) -> None:
    try:
        sys.exit(run_cli(argv))
    except SystemExit as exc:
        raise exc


if __name__ == "__main__":
    main()
