#!/usr/bin/env python3
"""
R-SOAK-02: in-process suite repeat soak (working-set growth bounds).

Usage (from repo root):
  python tests/regression/run_soak_inprocess.py
  python tests/regression/run_soak_inprocess.py --repeat 50
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUITE = REPO / "tests" / "fixtures" / "suites" / "soak_inprocess.toml"
CONFIG = REPO / "tests" / "fixtures" / "core.toml"
PROBE = REPO / "tests" / "fixtures" / "scripts" / "soak_probe.py"
SUMMARY_PASS = "Overall result: PASS"

WARMUP_ROWS = 10
WINDOW_ROWS = 10
MAX_RSS_DELTA_MB = 8.0
MAX_GC_OBJECTS_DELTA = 20_000
MAX_COLOSSEUM_OBJECTS_DELTA = 500


@dataclass(frozen=True)
class SoakRow:
    repeat_index: int
    rss_mb: float
    gc_objects: int
    colosseum_objects: int
    resource_cache_len: int


def _mean(values: list[float | int]) -> float:
    return sum(values) / len(values)


def _load_metrics(path: Path) -> list[SoakRow]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        raise ValueError(f"expected header plus data rows in {path}")
    rows: list[SoakRow] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        repeat_index, rss_mb, gc_objects, colosseum_objects, cache_len = line.split("\t")
        rows.append(
            SoakRow(
                repeat_index=int(repeat_index),
                rss_mb=float(rss_mb),
                gc_objects=int(gc_objects),
                colosseum_objects=int(colosseum_objects),
                resource_cache_len=int(cache_len),
            ),
        )
    return rows


def _check_growth(rows: list[SoakRow]) -> list[str]:
    failures: list[str] = []
    required = WARMUP_ROWS + WINDOW_ROWS
    if len(rows) < required:
        failures.append(f"expected at least {required} metric rows, got {len(rows)}")
        return failures

    for row in rows:
        if row.resource_cache_len != 0:
            failures.append(
                f"repeat {row.repeat_index}: resource_cache_len={row.resource_cache_len}",
            )

    warmup = rows[WARMUP_ROWS : WARMUP_ROWS + WINDOW_ROWS]
    tail = rows[-WINDOW_ROWS:]
    rss_delta = _mean([row.rss_mb for row in tail]) - _mean([row.rss_mb for row in warmup])
    gc_delta = _mean([row.gc_objects for row in tail]) - _mean(
        [row.gc_objects for row in warmup],
    )
    col_delta = _mean([row.colosseum_objects for row in tail]) - _mean(
        [row.colosseum_objects for row in warmup],
    )

    if rss_delta > MAX_RSS_DELTA_MB:
        failures.append(
            f"RSS grew {rss_delta:.2f} MiB from warmup window to tail "
            f"(limit {MAX_RSS_DELTA_MB} MiB)",
        )
    if gc_delta > MAX_GC_OBJECTS_DELTA:
        failures.append(
            f"gc object count grew {gc_delta:.0f} "
            f"(limit {MAX_GC_OBJECTS_DELTA})",
        )
    if col_delta > MAX_COLOSSEUM_OBJECTS_DELTA:
        failures.append(
            f"colosseum object count grew {col_delta:.0f} "
            f"(limit {MAX_COLOSSEUM_OBJECTS_DELTA})",
        )
    return failures


def _latest_run_dir(outputs: Path) -> Path | None:
    runs = sorted(outputs.glob("*"), key=lambda path: path.stat().st_mtime)
    return runs[-1] if runs else None


def _write_suite(path: Path, *, repeat_count: int) -> None:
    if not PROBE.is_file():
        raise FileNotFoundError(f"Soak probe script not found: {PROBE}")
    probe_path = PROBE.as_posix()
    text = (
        'name = "soak_inprocess"\n\n'
        f'tests = [{{ path = "{probe_path}", repeat_count = {repeat_count} }}]\n'
    )
    path.write_text(text, encoding="utf-8")


def _run_suite_inprocess(suite_path: Path, config_path: Path, *, cwd: Path) -> int:
    from colosseum.runner.cli import run_cli

    argv = [
        "run-suite",
        str(suite_path.resolve()),
        "--config",
        str(config_path.resolve()),
    ]
    try:
        return run_cli(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Core in-process soak: repeat_count growth")
    parser.add_argument("--repeat", type=int, default=100, help="repeat_count (default 100)")
    parser.add_argument("--suite", type=Path, default=SUITE)
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args(argv)

    if args.repeat < WARMUP_ROWS + WINDOW_ROWS:
        print(
            f"--repeat must be at least {WARMUP_ROWS + WINDOW_ROWS}, got {args.repeat}",
            file=sys.stderr,
        )
        return 2
    if not args.config.is_file():
        print(f"Config not found: {args.config}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    os.environ.update(env)

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="colosseum_soak_inprocess_") as tmp:
        cwd = Path(tmp)
        suite_path = cwd / "soak_inprocess.toml"
        _write_suite(suite_path, repeat_count=args.repeat)

        previous = os.getcwd()
        try:
            os.chdir(cwd)
            exit_code = _run_suite_inprocess(suite_path, args.config, cwd=cwd)
        finally:
            os.chdir(previous)

        if exit_code != 0:
            failures.append(f"run-suite exit {exit_code}")

        outputs = cwd / "outputs"
        run_dir = _latest_run_dir(outputs) if outputs.is_dir() else None
        if run_dir is None:
            failures.append("no run directory under outputs/")
        else:
            summary_path = run_dir / "summary.txt"
            if not summary_path.is_file():
                failures.append("missing summary.txt")
            elif SUMMARY_PASS not in summary_path.read_text(encoding="utf-8", errors="replace"):
                failures.append(f"summary.txt missing `{SUMMARY_PASS}`")

            metrics_path = run_dir / "soak_metrics.tsv"
            if not metrics_path.is_file():
                failures.append("missing soak_metrics.tsv from soak_probe.py")
            else:
                try:
                    rows = _load_metrics(metrics_path)
                except ValueError as exc:
                    failures.append(str(exc))
                else:
                    failures.extend(_check_growth(rows))

    if failures:
        print(f"INPROCESS SOAK FAIL: {len(failures)} issue(s)", file=sys.stderr)
        for item in failures[:10]:
            print(item, file=sys.stderr)
        if len(failures) > 10:
            print(f"... and {len(failures) - 10} more", file=sys.stderr)
        return 1

    print(
        f"INPROCESS SOAK PASS: repeat_count={args.repeat} "
        f"(R-SOAK-02, RSS delta <= {MAX_RSS_DELTA_MB} MiB after warmup)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
