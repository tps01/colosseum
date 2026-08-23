from __future__ import annotations

from colosseum.compatibility.entry_points import entry_points_for_group
from colosseum.logging import get_logger

from .registry import PluginRegistrationError, PluginRegistry

_logger = get_logger("colosseum.plugins")


def ensure_plugins_loaded(registry: PluginRegistry) -> None:
    """Load plugins registered under the ``colosseum.plugins`` entry-point group.

    First-party and third-party plugins are discovered the same way: installed
    distribution metadata must expose entry points (for example via
    ``pip install -e .``). Source trees without install metadata load no plugins.

    :param registry: Registry that receives plugin registrations.
    :type registry: PluginRegistry
    :raises PluginRegistrationError: On namespace/section collisions or when a
        plugin ``register()`` callable raises for any other reason.
    """
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
                f"Failed to load plugin entry point `{ep.name}`: {exc}"
            ) from exc

    registry.loaded = True
    _logger.debug(
        "Plugin registry ready: %d config section(s)",
        len(registry.config_section_specs()),
    )
