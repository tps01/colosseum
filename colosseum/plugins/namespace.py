from __future__ import annotations

import types
from typing import Any

from ..context import get_context
from .loader import ensure_plugins_loaded


class LazyNamespaceProxy:
    """Resolves `col.equipment.*` / `col.shared.*` after plugins register."""

    def __init__(self, name: str) -> None:
        self._name = name

    def _module(self) -> types.ModuleType:
        ctx = get_context()
        ensure_plugins_loaded(ctx.plugin_registry)
        return ctx.plugin_registry.get_namespace(self._name)

    def __getattr__(self, attr: str) -> Any:  # noqa: ANN401
        return getattr(self._module(), attr)

    def __dir__(self) -> list[str]:
        try:
            return dir(self._module())
        except Exception:
            return []
