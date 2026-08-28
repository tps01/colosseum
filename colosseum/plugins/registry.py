from __future__ import annotations

import sys
import types
from collections import defaultdict
from typing import Callable

from colosseum.logging import get_logger

from ..config.sections import ConfigSectionSpec, ConfigValidator

_logger = get_logger("colosseum.plugins")


class PluginRegistrationError(RuntimeError):
    """Raised when plugin registration would make runtime behavior ambiguous."""


class PluginRegistry:
    def __init__(self) -> None:
        self._sections: dict[str, ConfigSectionSpec] = {}
        self._validators: dict[str, list[ConfigValidator]] = defaultdict(list)
        self._namespaces: dict[str, types.ModuleType] = {}
        self._shutdown_hooks: list[Callable[[], None]] = []
        self._loaded = False

    def register_config_section(self, spec: ConfigSectionSpec) -> None:
        """Register one bench TOML section (one dotted path and one ID field).

        Call this once per table type. Duplicate ``dotted_path`` values raise;
        use ``replace_config_section()`` for an intentional override.

        :param spec: Section contract (one path, one id field, any number of keys).
        :type spec: ConfigSectionSpec

        :raises PluginRegistrationError: When ``spec.dotted_path`` is already registered.
        """
        if spec.dotted_path in self._sections:
            raise PluginRegistrationError(
                f"Config section `{spec.dotted_path}` is already registered. "
                "Use replace_config_section() for an intentional override."
            )
        self._sections[spec.dotted_path] = spec

    def replace_config_section(self, spec: ConfigSectionSpec) -> None:
        if spec.dotted_path not in self._sections:
            _logger.warning("Replacing unregistered config section `%s`", spec.dotted_path)
        self._sections[spec.dotted_path] = spec

    def register_config_validator(self, dotted_path: str, validator: ConfigValidator) -> None:
        self._validators[dotted_path].append(validator)

    def register_namespace(self, name: str, module: types.ModuleType) -> None:
        if name in self._namespaces:
            raise PluginRegistrationError(
                f"Namespace `{name}` is already registered. "
                "Use replace_namespace() for an intentional override."
            )
        self._namespaces[name] = module
        self._ensure_evidence_domain(module, name)
        _logger.debug("Registered namespace `%s`", name)

    def replace_namespace(self, name: str, module: types.ModuleType) -> None:
        if name not in self._namespaces:
            _logger.warning("Replacing unregistered namespace `%s`", name)
        self._namespaces[name] = module
        self._ensure_evidence_domain(module, name)

    def register_shutdown(self, hook: Callable[[], None]) -> None:
        self._shutdown_hooks.append(hook)

    def config_section_specs(self) -> list[ConfigSectionSpec]:
        return list(self._sections.values())

    def validators_for(self, dotted_path: str) -> list[ConfigValidator]:
        return self._validators.get(dotted_path, [])

    def get_namespace(self, name: str) -> types.ModuleType:
        if name not in self._namespaces:
            raise RuntimeError(
                f"Namespace `{name}` is not registered. Install the plugin package "
                "that provides it (same environment as colosseum-core) and ensure it "
                "exposes a colosseum.plugins entry point."
            )
        return self._namespaces[name]

    def has_namespace(self, name: str) -> bool:
        return name in self._namespaces

    def run_shutdown(self) -> None:
        for hook in reversed(self._shutdown_hooks):
            try:
                hook()
            except Exception:
                _logger.exception("Plugin shutdown hook failed")

    @staticmethod
    def _ensure_evidence_domain(module: types.ModuleType, name: str) -> None:
        """Default evidence domain to *name* when the plugin has not set one."""
        module_name = getattr(module, "__name__", "") or ""
        parts = module_name.split(".") if module_name else []
        for depth in range(len(parts), 0, -1):
            parent = sys.modules.get(".".join(parts[:depth]))
            if parent is None:
                continue
            if getattr(parent, "__colosseum_domain__", None):
                return
        if getattr(module, "__colosseum_domain__", None):
            return
        top = parts[0] if parts else ""
        if top and top in sys.modules:
            sys.modules[top].__colosseum_domain__ = name  # type: ignore[attr-defined]
        else:
            module.__colosseum_domain__ = name  # type: ignore[attr-defined]

    @property
    def loaded(self) -> bool:
        return self._loaded

    @loaded.setter
    def loaded(self, value: bool) -> None:
        self._loaded = value
