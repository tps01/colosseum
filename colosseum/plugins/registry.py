from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from colosseum.decorators._common import stamp_evidence_domain
from colosseum.logging import get_logger

if TYPE_CHECKING:
    import types

    from colosseum.config.sections import ConfigSectionSpec

_logger = get_logger("colosseum.plugins")


class PluginRegistrationError(RuntimeError):
    """Raised when plugin registration would make runtime behavior ambiguous."""


class PluginRegistry:
    def __init__(self) -> None:
        self._sections: dict[str, ConfigSectionSpec] = {}
        self._namespaces: dict[str, types.ModuleType] = {}
        self._shutdown_hooks: list[Callable[[], None]] = []
        self._loaded = False

    def register_config_section(self, spec: ConfigSectionSpec) -> None:
        if spec.dotted_path in self._sections:
            raise PluginRegistrationError(
                f"Config section `{spec.dotted_path}` is already registered.",
            )
        self._sections[spec.dotted_path] = spec

    def register_namespace(self, name: str, module: types.ModuleType) -> None:
        if name in self._namespaces:
            raise PluginRegistrationError(f"Namespace `{name}` is already registered.")
        self._namespaces[name] = module
        stamp_evidence_domain(module, name)
        _logger.debug("Registered namespace `%s`", name)

    def register_shutdown(self, hook: Callable[[], None]) -> None:
        self._shutdown_hooks.append(hook)

    def config_section_specs(self) -> list[ConfigSectionSpec]:
        return list(self._sections.values())

    def get_namespace(self, name: str) -> types.ModuleType:
        if name not in self._namespaces:
            raise RuntimeError(
                f"Namespace `{name}` is not registered. Install the plugin package "
                "that provides it (same environment as colosseum-core) and ensure it "
                "exposes a colosseum.plugins entry point.",
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

    @property
    def loaded(self) -> bool:
        return self._loaded

    @loaded.setter
    def loaded(self, value: bool) -> None:
        self._loaded = value
