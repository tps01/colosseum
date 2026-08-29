from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Protocol, cast

from colosseum.logging import get_logger

from .registry import PluginRegistrationError, PluginRegistry

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = get_logger("colosseum.plugins")


class ColosseumPluginEntryPoint(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def value(self) -> str: ...

    def load(self) -> Callable[..., object]: ...


def _discovered_for_group(group: str) -> list[ColosseumPluginEntryPoint]:
    discovered = entry_points()
    select = getattr(discovered, "select", None)
    if select is not None:
        return cast("list[ColosseumPluginEntryPoint]", list(select(group=group)))
    get = getattr(discovered, "get", None)
    if get is not None:
        return cast("list[ColosseumPluginEntryPoint]", list(get(group, [])))
    return cast(
        "list[ColosseumPluginEntryPoint]",
        [ep for ep in discovered if getattr(ep, "group", None) == group],
    )


def _dedupe_entry_points(
    discovered: list[ColosseumPluginEntryPoint],
) -> list[ColosseumPluginEntryPoint]:
    unique: list[ColosseumPluginEntryPoint] = []
    seen: set[tuple[str, str]] = set()
    for entry_point in discovered:
        key = (entry_point.name, str(getattr(entry_point, "value", "") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry_point)
    return unique


def entry_points_for_group(group: str) -> list[ColosseumPluginEntryPoint]:
    return _dedupe_entry_points(_discovered_for_group(group))


def ensure_plugins_loaded(registry: PluginRegistry) -> None:
    if registry.loaded:
        return

    eps = entry_points_for_group("colosseum.plugins")
    for ep in eps:
        try:
            plugin_register = ep.load()
            plugin_register(registry)
            _logger.debug("Loaded plugin entry point: %s", ep.name)
        except PluginRegistrationError:
            raise
        except Exception as exc:
            _logger.exception("Failed to load plugin entry point `%s`", ep.name)
            raise PluginRegistrationError(
                f"Failed to load plugin entry point `{ep.name}`: {exc}",
            ) from exc

    registry.loaded = True
    _logger.debug(
        "Plugin registry ready: %d config section(s)",
        len(registry.config_section_specs()),
    )
