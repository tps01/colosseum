"""Non-fixture helpers imported by unit, integration, and e2e tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_CONFIG = REPO_ROOT / "tests" / "fixtures" / "core.toml"
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def run_endex_expect_code(expected: int) -> None:
    from colosseum.results import endex

    with pytest.raises(SystemExit) as exc_info:
        endex()
    code = exc_info.value.code
    if code is None:
        code = 0
    assert code == expected, f"expected exit {expected}, got {code}"


def latest_output_dir(cwd: Path) -> Path:
    """Return the newest top-level entry under ``outputs/`` (usually a suite container)."""
    outputs = cwd / "outputs"
    assert outputs.is_dir(), f"outputs/ was not created under {cwd}"
    runs = sorted(outputs.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    assert runs, f"outputs/ is empty under {cwd}"
    return runs[0]


def latest_suite_container(cwd: Path) -> Path:
    return latest_output_dir(cwd)


def list_slot_dirs(container: Path) -> list[Path]:
    return sorted(
        (p for p in container.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    )


def slot_dirs_matching(container: Path, script_stem: str) -> list[Path]:
    sanitized = script_stem.replace(".", "_")
    return [p for p in list_slot_dirs(container) if f"_{sanitized}" in p.name or p.name.endswith(sanitized)]


def query_db_optional(run_dir: Path, sql: str, params: tuple = ()) -> list[tuple[Any, ...]]:
    db_path = run_dir / "execution.sqlite"
    if not db_path.is_file():
        return []
    return query_db(run_dir, sql, params)


def query_db(run_dir: Path, sql: str, params: tuple = ()) -> list[tuple[Any, ...]]:
    db_path = run_dir / "execution.sqlite"
    assert db_path.is_file(), f"missing database in {run_dir}"
    conn = sqlite3.connect(db_path)
    try:
        return list(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def verification_row(run_dir: Path, key: str) -> tuple[Any, ...] | None:
    rows = query_db(
        run_dir,
        "SELECT status, optional, domain FROM verifications WHERE key=? ORDER BY id DESC LIMIT 1",
        (key,),
    )
    return rows[0] if rows else None
