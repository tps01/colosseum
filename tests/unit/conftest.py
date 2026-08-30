"""Unit-tier pytest fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import colosseum.context as context_module
from colosseum.database.manager import DatabaseManager
from colosseum.database.schema import SCHEMA_SQL
from colosseum.plugins.loader import ensure_plugins_loaded
from colosseum.plugins.registry import PluginRegistry

from tests.unit.db_unit import UNIT_TEST_DB_URI, connect_unit_test_db, truncate_unit_test_db
from tests.unit.fast_bootstrap import fast_ensure_plugins_loaded, make_initialize_from_template

pytest_plugins = ["tests.support.common_fixtures"]


@pytest.fixture(scope="session")
def unit_test_db() -> sqlite3.Connection:
    # Hold one connection open so shared in-memory schema survives the session.
    keeper = sqlite3.connect(UNIT_TEST_DB_URI, uri=True)
    keeper.executescript(SCHEMA_SQL)
    keeper.commit()
    yield keeper
    keeper.close()


@pytest.fixture(scope="session")
def unit_test_db_uri(unit_test_db: sqlite3.Connection) -> str:
    return UNIT_TEST_DB_URI


@pytest.fixture(scope="session")
def session_plugin_registry() -> PluginRegistry:
    """Load entry points once per pytest process (amortized across mutants)."""
    registry = PluginRegistry()
    ensure_plugins_loaded(registry)
    return registry


@pytest.fixture(scope="session")
def empty_sqlite_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Prebuilt empty execution DB; file copies replace per-test executescript."""
    path = tmp_path_factory.mktemp("sqlite_template") / "empty.sqlite"
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    return path


@pytest.fixture(autouse=True)
def _fast_unit_plugin_seed(
    session_plugin_registry: PluginRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seed registries from the session load; keep loader.ensure_plugins_loaded real."""

    def _ensure(registry: PluginRegistry) -> None:
        fast_ensure_plugins_loaded(registry, session_registry=session_plugin_registry)

    # Patch call sites used by runtime bootstrap, not the loader unit under test.
    monkeypatch.setattr("colosseum.config.loader.ensure_plugins_loaded", _ensure)
    monkeypatch.setattr("colosseum.plugins.namespace.ensure_plugins_loaded", _ensure)


@pytest.fixture(autouse=True)
def _fast_unit_db_initialize(
    empty_sqlite_template: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        DatabaseManager,
        "initialize",
        make_initialize_from_template(empty_sqlite_template),
    )


@pytest.fixture
def db(unit_test_db: sqlite3.Connection, unit_test_db_uri: str) -> DatabaseManager:
    truncate_unit_test_db(unit_test_db)
    manager = DatabaseManager()
    connect_unit_test_db(manager, unit_test_db_uri)
    try:
        yield manager
    finally:
        manager.close()
        truncate_unit_test_db(unit_test_db)


@pytest.fixture
def unit_runtime_context(
    tmp_path,
    unit_test_db: sqlite3.Connection,
    unit_test_db_uri: str,
) -> context_module.RuntimeContext:
    truncate_unit_test_db(unit_test_db)
    ctx = context_module.init_context(test_case_name="unit")
    ctx.output_dir = tmp_path
    connect_unit_test_db(ctx.db, unit_test_db_uri)
    try:
        yield ctx
    finally:
        ctx.db.close()
        truncate_unit_test_db(unit_test_db)


@pytest.fixture
def io_runtime_context(
    tmp_path,
    unit_test_db: sqlite3.Connection,
    unit_test_db_uri: str,
    request: pytest.FixtureRequest,
) -> context_module.RuntimeContext:
    """In-memory runtime with output dir for I/O plugin unit tests."""
    truncate_unit_test_db(unit_test_db)
    name = request.node.name.removeprefix("test_")
    ctx = context_module.init_context(test_case_name=name)
    ctx.output_dir = tmp_path
    connect_unit_test_db(ctx.db, unit_test_db_uri)
    try:
        yield ctx
    finally:
        ctx.db.close()
        truncate_unit_test_db(unit_test_db)


@pytest.fixture
def io_bench(tmp_path: Path):
    """Write a config TOML snippet under ``tmp_path`` and return its path."""

    def _write(body: str) -> Path:
        path = tmp_path / "config.toml"
        path.write_text(body.strip() + "\n", encoding="utf-8")
        return path

    return _write
