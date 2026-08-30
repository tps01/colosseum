"""
Profile Colosseum pytest paths to find slow code (stdlib cProfile).

Used by profile_tests.py; importable for ad-hoc analysis.
"""

from __future__ import annotations

import cProfile
import pstats
import re
import time
from dataclasses import dataclass
from io import StringIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

_PACKAGES_RE = r"colosseum[\\/]"
_TEST_DIR_RES: dict[str, str] = {
    "unit": r"tests[\\/]unit",
    "integration": r"tests[\\/]integration",
    "e2e": r"tests[\\/]e2e",
}


@dataclass(frozen=True)
class ProfileReport:
    exit_code: int
    wall_seconds: float
    stats_path: Path | None
    summary_text: str


def _format_stats(
    profiler: cProfile.Profile,
    *,
    sort_key: str,
    limit: int,
    restriction: str | int | None,
    strip_dirs: bool,
) -> str:
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    if strip_dirs:
        stats.strip_dirs()
    stats.sort_stats(sort_key)
    if restriction is None:
        stats.print_stats(limit)
    else:
        stats.print_stats(restriction, limit)
    return stream.getvalue()


def _project_path_re(test_paths: Sequence[str]) -> str:
    test_parts: list[str] = []
    for path in test_paths:
        normalized = path.replace("\\", "/").strip("/")
        if normalized == "tests/unit" or normalized.endswith("/unit"):
            test_parts.append(_TEST_DIR_RES["unit"])
        elif normalized == "tests/integration" or normalized.endswith("/integration"):
            test_parts.append(_TEST_DIR_RES["integration"])
        elif normalized == "tests/e2e" or normalized.endswith("/e2e"):
            test_parts.append(_TEST_DIR_RES["e2e"])
        else:
            escaped = re.escape(path).replace(r"\\", r"[\\/]")
            test_parts.append(escaped)
    tests_re = "|".join(test_parts) if test_parts else r"tests[\\/]"
    return f"({_PACKAGES_RE}|{tests_re})"


def _project_label(test_paths: Sequence[str]) -> str:
    labels: list[str] = []
    for path in test_paths:
        normalized = path.replace("\\", "/").strip("/")
        if normalized.startswith("tests/"):
            labels.append(normalized.removeprefix("tests/"))
        else:
            labels.append(normalized)
    return ", ".join(labels) if labels else "project paths"


def profile_pytest(
    repo_root: Path,
    test_paths: Sequence[str],
    *,
    pytest_args: Iterable[str] | None = None,
    marker_args: Iterable[str] | None = None,
    sort: str = "cumulative",
    limit: int = 40,
    project_only: bool = True,
    strip_dirs: bool = False,
    save_stats: Path | None = None,
) -> ProfileReport:
    """Run pytest on ``test_paths`` under cProfile and return a text summary.

    :param repo_root: Repository root (reserved for future chdir checks).
    :type repo_root: Path
    :param test_paths: Pytest path arguments (e.g. ``tests/unit``).
    :type test_paths: Sequence[str]
    :param pytest_args: Extra pytest CLI arguments.
    :type pytest_args: Iterable[str] | None, optional
    :param marker_args: Optional pytest marker expression arguments.
    :type marker_args: Iterable[str] | None, optional
    :param sort: pstats sort key (``cumulative``, ``tottime``, etc.).
    :type sort: str
    :param limit: Rows per stats table.
    :type limit: int
    :param project_only: Include project-scoped pstats tables.
    :type project_only: bool
    :param strip_dirs: Strip path prefixes in pstats output.
    :type strip_dirs: bool
    :param save_stats: Optional path to write ``.prof`` for snakeviz.
    :type save_stats: Path | None, optional

    :returns: Profile report with exit code and summary text.
    :rtype: ProfileReport
    """
    import pytest

    _ = repo_root
    args = [*test_paths, "-q", "--durations=15"]
    if marker_args:
        args.extend(marker_args)
    if pytest_args:
        args.extend(pytest_args)

    profiler = cProfile.Profile()
    started = time.perf_counter()
    profiler.enable()
    try:
        exit_code = pytest.main([*args])
    finally:
        profiler.disable()
    wall = time.perf_counter() - started

    if save_stats is not None:
        save_stats.parent.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(save_stats))

    project_re = _project_path_re(test_paths)
    project_label = _project_label(test_paths)
    sections = [
        f"Wall time: {wall:.3f}s",
        f"Pytest exit code: {exit_code}",
        f"Test paths: {', '.join(test_paths)}",
        "",
        f"=== Top {limit} by {sort} (all paths) ===",
        _format_stats(
            profiler,
            sort_key=sort,
            limit=limit,
            restriction=None,
            strip_dirs=strip_dirs,
        ),
    ]
    if project_only:
        sections.extend(
            [
                "",
                f"=== Top {limit} by {sort} (project: {project_label}) ===",
                _format_stats(
                    profiler,
                    sort_key=sort,
                    limit=limit,
                    restriction=project_re,
                    strip_dirs=strip_dirs,
                ),
                "",
                f"=== Top {limit} by tottime (self time, project only) ===",
                _format_stats(
                    profiler,
                    sort_key="tottime",
                    limit=limit,
                    restriction=project_re,
                    strip_dirs=strip_dirs,
                ),
            ],
        )

    return ProfileReport(
        exit_code=int(exit_code),
        wall_seconds=wall,
        stats_path=save_stats,
        summary_text="\n".join(sections),
    )


def profile_pytest_unit_tests(
    repo_root: Path,
    *,
    pytest_args: Iterable[str] | None = None,
    sort: str = "cumulative",
    limit: int = 40,
    project_only: bool = True,
    strip_dirs: bool = False,
    save_stats: Path | None = None,
) -> ProfileReport:
    """Backward-compatible wrapper for ``tests/unit`` only."""
    return profile_pytest(
        repo_root,
        ("tests/unit",),
        pytest_args=pytest_args,
        sort=sort,
        limit=limit,
        project_only=project_only,
        strip_dirs=strip_dirs,
        save_stats=save_stats,
    )
