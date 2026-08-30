"""I-PLG-01: runtime plugins load via entry points."""

from __future__ import annotations

import types

import colosseum.plugins.loader as loader
from colosseum.config.sections import ConfigSectionSpec
from colosseum.plugins.loader import ensure_plugins_loaded
from colosseum.plugins.registry import PluginRegistry


class _EntryPoint:
    name = "acme"

    @staticmethod
    def load():
        def register(registry: PluginRegistry) -> None:
            registry.register_config_section(
                ConfigSectionSpec(dotted_path="acme.device", id_field="device_id")
            )
            registry.register_namespace("acme", types.ModuleType("acme_api"))

        return register


def test_entry_point_registers_plugin_specification(monkeypatch) -> None:
    monkeypatch.setattr(loader, "entry_points_for_group", lambda _group: [_EntryPoint()])
    registry = PluginRegistry()

    ensure_plugins_loaded(registry)

    assert [spec.dotted_path for spec in registry.config_section_specs()] == ["acme.device"]
    assert registry.has_namespace("acme")
    assert registry.loaded
