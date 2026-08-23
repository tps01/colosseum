"""Third-party namespace access via colosseum.__getattr__."""

from __future__ import annotations

import types

import colosseum as col
import colosseum.context as context_module
from colosseum.context import init_context, get_context


def test_getattr_returns_lazy_proxy_for_unregistered_name() -> None:
    proxy = col.acme_stub_namespace
    assert proxy._name == "acme_stub_namespace"  # noqa: SLF001


def test_third_party_namespace_resolves_after_register() -> None:
    context_module._ACTIVE_CONTEXT = None
    init_context(test_case_name="plugin_namespace")
    ctx = get_context()

    stub_api = types.ModuleType("stub_api")

    def measure_stub(*, key: str) -> float:
        return 1.0

    stub_api.measure_stub = measure_stub  # type: ignore[attr-defined]
    ctx.plugin_registry.register_namespace("acme_stub", stub_api)
    ctx.plugin_registry.loaded = True

    assert col.acme_stub.measure_stub(key="x") == 1.0
