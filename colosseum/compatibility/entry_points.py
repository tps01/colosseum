from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

try:
    from importlib.metadata import entry_points
except ImportError:  # pragma: no cover
    from importlib_metadata import entry_points  # type: ignore[import-not-found,no-redef]


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
        return cast(list[ColosseumPluginEntryPoint], list(select(group=group)))
    get = getattr(discovered, "get", None)
    if get is not None:
        return cast(list[ColosseumPluginEntryPoint], list(get(group, [])))
    return cast(
        list[ColosseumPluginEntryPoint],
        [ep for ep in discovered if getattr(ep, "group", None) == group],
    )


def _dedupe_entry_points(
    discovered: list[ColosseumPluginEntryPoint],
) -> list[ColosseumPluginEntryPoint]:
    """Drop identical ``(name, value)`` duplicates while preserving order.

    Editable installs can surface both ``.dist-info`` and ``.egg-info`` metadata
    (especially when the project root is on ``sys.path``), which makes
    ``importlib.metadata`` report the same plugin entry point twice on some
    Python versions.
    """
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
    """Return entry points for *group* (importlib.metadata compatibility shim).

    :param group: Entry-point group name (for example ``colosseum.plugins``).
    :type group: str

    :returns: Discovered entry points for the group (empty when none are installed).
    :rtype: list[ColosseumPluginEntryPoint]
    """
    return _dedupe_entry_points(_discovered_for_group(group))
