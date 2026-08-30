"""U-PLG-01: plugin registry specifications."""

from __future__ import annotations

import sys
import types
from collections.abc import Callable

import pytest
from colosseum.config.sections import ConfigSectionSpec
from colosseum.decorators._common import resolve_domain
from colosseum.plugins import loader
from colosseum.plugins.loader import ensure_plugins_loaded
from colosseum.plugins.registry import PluginRegistrationError, PluginRegistry


def test_shutdown_hooks_run_in_reverse_order() -> None:
    reg = PluginRegistry()
    order: list[int] = []
    reg.register_shutdown(lambda: order.append(1))
    reg.register_shutdown(lambda: order.append(2))
    reg.run_shutdown()
    assert order == [2, 1]


def test_duplicate_section_spec_fails_fast() -> None:
    reg = PluginRegistry()
    spec = ConfigSectionSpec("equipment.psu", "psu_id", ("driver",))
    reg.register_config_section(spec)
    with pytest.raises(PluginRegistrationError, match="already registered"):
        reg.register_config_section(spec)



def test_config_section_specs_is_a_snapshot() -> None:
    reg = PluginRegistry()
    spec = ConfigSectionSpec("equipment.psu", "psu_id", ("driver",))
    reg.register_config_section(spec)
    listed = reg.config_section_specs()
    listed.clear()
    assert reg.config_section_specs() == [spec]


def test_duplicate_namespace_fails_fast() -> None:
    reg = PluginRegistry()
    module = types.ModuleType("plugin")
    reg.register_namespace("equipment", module)
    with pytest.raises(PluginRegistrationError, match="already registered"):
        reg.register_namespace("equipment", module)



def test_loader_loads_entry_points(monkeypatch: pytest.MonkeyPatch) -> None:
    class SampleEntryPoint:
        name = "equipment"

        def load(self) -> Callable[[PluginRegistry], None]:
            def register(registry: PluginRegistry) -> None:
                registry.register_namespace("equipment", types.ModuleType("equipment"))

            return register

    monkeypatch.setattr(loader, "entry_points_for_group", lambda _group: [SampleEntryPoint()])
    reg = PluginRegistry()
    ensure_plugins_loaded(reg)
    assert reg.has_namespace("equipment")


def test_register_namespace_sets_evidence_domain_when_unset() -> None:
    reg = PluginRegistry()
    module = types.ModuleType("acme_plugin_api")
    reg.register_namespace("acme", module)
    assert module.__colosseum_domain__ == "acme"


def test_register_namespace_preserves_existing_evidence_domain() -> None:
    reg = PluginRegistry()
    package = types.ModuleType("vendor_pkg")
    package.__colosseum_domain__ = "custom"
    sys.modules["vendor_pkg"] = package
    try:
        api = types.ModuleType("vendor_pkg.api")
        api.__name__ = "vendor_pkg.api"
        sys.modules["vendor_pkg.api"] = api
        reg.register_namespace("vendor", api)
        assert package.__colosseum_domain__ == "custom"
        assert not hasattr(api, "__colosseum_domain__")
    finally:
        sys.modules.pop("vendor_pkg.api", None)
        sys.modules.pop("vendor_pkg", None)


def test_register_namespace_domain_is_visible_to_resolve_domain() -> None:
    reg = PluginRegistry()
    package = types.ModuleType("auto_domain_pkg")
    sys.modules["auto_domain_pkg"] = package
    try:
        api = types.ModuleType("auto_domain_pkg.api")
        api.__name__ = "auto_domain_pkg.api"
        sys.modules["auto_domain_pkg.api"] = api
        reg.register_namespace("autodemo", api)

        def sample() -> None:
            return None

        sample.__module__ = "auto_domain_pkg.api"
        assert resolve_domain(sample) == "autodemo"
    finally:
        sys.modules.pop("auto_domain_pkg.api", None)
        sys.modules.pop("auto_domain_pkg", None)


def test_get_namespace_error_does_not_assume_colosseum_prefix() -> None:
    reg = PluginRegistry()
    with pytest.raises(RuntimeError, match="same environment as colosseum-core"):
        reg.get_namespace("missing")


def test_loader_fails_fast_on_register_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenEntryPoint:
        name = "broken"

        def load(self) -> Callable[[PluginRegistry], None]:
            def register(_registry: PluginRegistry) -> None:
                raise RuntimeError("boom")

            return register

    monkeypatch.setattr(loader, "entry_points_for_group", lambda _group: [BrokenEntryPoint()])
    reg = PluginRegistry()
    with pytest.raises(PluginRegistrationError, match="Failed to load plugin entry point `broken`"):
        ensure_plugins_loaded(reg)
    assert reg.loaded is False


def test_loader_fails_fast_on_namespace_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    class FirstEntryPoint:
        name = "first"

        def load(self) -> Callable[[PluginRegistry], None]:
            def register(registry: PluginRegistry) -> None:
                registry.register_namespace("equipment", types.ModuleType("first"))

            return register

    class CollidingEntryPoint:
        name = "vendor_equipment"

        def load(self) -> Callable[[PluginRegistry], None]:
            def register(registry: PluginRegistry) -> None:
                registry.register_namespace("equipment", types.ModuleType("vendor"))

            return register

    monkeypatch.setattr(
        loader,
        "entry_points_for_group",
        lambda _group: [FirstEntryPoint(), CollidingEntryPoint()],
    )
    reg = PluginRegistry()
    with pytest.raises(PluginRegistrationError, match="already registered"):
        ensure_plugins_loaded(reg)
