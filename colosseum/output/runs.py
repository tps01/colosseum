from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .paths import sanitize_logical_name


@dataclass(frozen=True)
class RunDirectoryEntry:
    path: Path
    outputs_dir: Path


def list_run_directories(cwd: Path) -> list[Path]:
    outputs_root = cwd / "outputs"
    if not outputs_root.is_dir():
        return []
    runs = [p for p in outputs_root.iterdir() if p.is_dir()]
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs


def find_output_directories(cwd: Path, *, max_depth: int = 2) -> list[Path]:
    """Find nearby ``outputs`` directories without unbounded recursion."""
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    outputs_dirs: list[Path] = []
    seen: set[Path] = set()
    frontier = [cwd]
    for depth in range(max_depth + 1):
        for parent in frontier:
            outputs_dir = parent / "outputs"
            if outputs_dir.is_dir() and outputs_dir not in seen:
                outputs_dirs.append(outputs_dir)
                seen.add(outputs_dir)
        if depth == max_depth:
            break

        next_frontier: list[Path] = []
        for parent in frontier:
            try:
                children = sorted(
                    (path for path in parent.iterdir() if path.is_dir()),
                    key=lambda path: path.name.lower(),
                )
            except OSError:
                continue
            next_frontier.extend(path for path in children if path.name != "outputs")
        frontier = next_frontier

    return outputs_dirs


def list_run_directory_entries(cwd: Path, *, max_depth: int = 2) -> list[RunDirectoryEntry]:
    entries: list[RunDirectoryEntry] = []
    for outputs_dir in find_output_directories(cwd, max_depth=max_depth):
        for run_dir in outputs_dir.iterdir():
            if run_dir.is_dir():
                entries.append(RunDirectoryEntry(path=run_dir, outputs_dir=outputs_dir))
    entries.sort(key=lambda entry: entry.path.stat().st_mtime, reverse=True)
    return entries


def _matches_logical_name(dir_name: str, logical_name: str) -> bool:
    sanitized = sanitize_logical_name(logical_name)
    if dir_name.endswith(f"_{sanitized}"):
        return True
    pattern = rf"^.*_{re.escape(sanitized)}(?:_\d+)?(?:-(?:pass|fail)(?:_\d+)?)?$"
    return bool(re.match(pattern, dir_name))


def _collect_run_candidates(
    outputs_root: Path, logical_name: str, since: float | None
) -> list[Path]:
    candidates: list[Path] = []
    for run_dir in outputs_root.iterdir():
        if not run_dir.is_dir():
            continue
        if since is not None and run_dir.stat().st_mtime < since:
            continue
        if _matches_logical_name(run_dir.name, logical_name):
            candidates.append(run_dir)
            continue
        try:
            children = [p for p in run_dir.iterdir() if p.is_dir()]
        except OSError:
            continue
        if not children:
            continue
        for child in children:
            if since is not None and child.stat().st_mtime < since:
                continue
            if _matches_logical_name(child.name, logical_name):
                candidates.append(child)
    return candidates


def find_run_directory(
    cwd: Path,
    logical_name: str,
    since: float | None = None,
) -> Path | None:
    outputs_root = cwd / "outputs"
    if not outputs_root.is_dir():
        return None

    candidates = _collect_run_candidates(outputs_root, logical_name, since)

    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def read_summary_json(run_dir: Path) -> dict[str, Any] | None:
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        return None
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload)
