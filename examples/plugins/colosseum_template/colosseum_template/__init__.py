"""Colosseum extension template — register() wires namespace (and optional config)."""

from colosseum.config.sections import ConfigSectionSpec
from colosseum.logging import get_logger
from colosseum.plugins.registry import PluginRegistry

# Evidence domain for @command / @measurement / @verification (rename when forking).
# register_namespace also defaults the domain to the namespace if this is unset.
__colosseum_domain__ = "template"

_logger = get_logger("colosseum.template")


def register(registry: PluginRegistry) -> None:
    from colosseum_template import api

    # Required: expose public API as col.template.* (TODO: rename namespace when forking).
    registry.register_namespace("template", api)
    _logger.debug("Registered col.template namespace")

    # Optional (Layer 2): one spec = one dotted path, one id field, any number of keys.
    # Call register_config_section again to own a second table type.
    registry.register_config_section(
        ConfigSectionSpec(
            dotted_path="template.device",
            id_field="device_id",
            required_keys=("serial",),
            optional_keys=("label",),
        )
    )

    # Optional (Layer 3): registry.register_shutdown(close_all)
