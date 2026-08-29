"""Entry point discovery via plugins loader."""

from __future__ import annotations

from importlib.metadata import distribution
from types import SimpleNamespace

from colosseum.plugins import loader as loader_module
from colosseum.plugins.loader import entry_points_for_group


def test_core_distribution_does_not_declare_runtime_plugins() -> None:
    plugin_names = {
        entry_point.name
        for entry_point in distribution("colosseum-core").entry_points
        if entry_point.group == "colosseum.plugins"
    }
    assert plugin_names == set()


def test_duplicate_plugin_entry_points_are_deduped(monkeypatch) -> None:
    duplicate = SimpleNamespace(name="shared", value="colosseum_shared:register")
    monkeypatch.setattr(
        loader_module,
        "_discovered_for_group",
        lambda _group: [duplicate, duplicate],
    )

    eps = entry_points_for_group("colosseum.plugins")

    assert eps == [duplicate]
