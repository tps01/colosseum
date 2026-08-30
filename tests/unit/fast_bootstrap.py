"""Mutation-friendly unit-test bootstrap: cheap clones, hard resets.

Session fixtures load plugins and schema once; each test gets a fresh
registry copy / DB file copy so order and subset runs stay isolated.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

from colosseum.database.manager import DatabaseManager
from colosseum.plugins.registry import PluginRegistry


def seed_registry(dest: PluginRegistry, source: PluginRegistry) -> None:
    """Copy registration state into ``dest`` without reloading entry points."""
    dest._sections = dict(source._sections)
    dest._namespaces = dict(source._namespaces)
    # Do not share shutdown hooks across tests.
    dest._shutdown_hooks = []
    dest._loaded = True


def fast_ensure_plugins_loaded(
    registry: PluginRegistry, *, session_registry: PluginRegistry
) -> None:
    if registry.loaded:
        return
    seed_registry(registry, session_registry)


def make_initialize_from_template(template_path: Path):
    """Return a ``DatabaseManager.initialize`` that copies a prebuilt empty DB."""

    def initialize(self: DatabaseManager, db_path: Path) -> None:
        if self._conn is not None:
            return
        self.defer_commits = os.environ.get("COLOSSEUM_DEFER_DB_COMMITS") == "1"
        path_str = str(db_path)
        if path_str == ":memory:":
            self._conn = sqlite3.connect(":memory:")
            from colosseum.database.schema import SCHEMA_SQL

            self._conn.executescript(SCHEMA_SQL)
            self._conn.commit()
            return
        dest = Path(db_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template_path, dest)
        self._conn = sqlite3.connect(str(dest))

    return initialize
