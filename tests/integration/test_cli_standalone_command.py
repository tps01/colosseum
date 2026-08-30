"""Integration tests for expanded CLI run modes."""

from __future__ import annotations

import types

import pytest

from colosseum.decorators import command
from colosseum.runner.cli import run_cli
from tests.support.helpers import latest_output_dir, query_db


@pytest.mark.requirement("E2E-RUN-11")
def test_standalone_command_run_writes_artifacts(
    monkeypatch,
    isolated_cwd,
    core_config,
) -> None:
    """Standalone ``-c`` produces command evidence and artifacts."""
    module = types.ModuleType("stub_api")

    @command
    def ping(*, key: str = "") -> None:
        return None

    module.ping = ping
    module.__colosseum_domain__ = "stub"

    import colosseum.plugins.loader as loader

    class _EntryPoint:
        name = "stub"

        @staticmethod
        def load():
            def register(registry):
                registry.register_namespace("stub", module)

            return register

    monkeypatch.setattr(loader, "entry_points_for_group", lambda _group: [_EntryPoint()])

    with pytest.raises(SystemExit) as exc:
        run_cli(
            [
                "run",
                "-c",
                "stub.ping,key=dev1",
                "-g",
                str(core_config),
            ],
        )
    assert exc.value.code == 0
    run_dir = latest_output_dir(isolated_cwd)
    rows = query_db(run_dir, "SELECT command, key FROM commands")
    assert rows == [("ping", "dev1")]
