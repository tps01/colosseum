Plugins and extensions
======================

Plugins are separate Python distributions discovered from setuptools entry points.
The copy-ready template is under ``examples/plugins/colosseum_template``.
``colosseum-shared`` is a minimal first-party example (namespace only).

A working plugin needs only three things. Config, evidence decorators, and resource
helpers are optional layers.

Layer 0 — Minimal plugin
------------------------

1. An installable package with a ``colosseum.plugins`` entry point.
2. ``register(registry)`` that calls ``register_namespace``.
3. An API module exposed as ``col.<namespace>.*``.

Example::

   # acme_bench/__init__.py
   from colosseum.logging import get_logger
   from colosseum.plugins.registry import PluginRegistry

   _logger = get_logger("colosseum.acme")

   def register(registry: PluginRegistry) -> None:
       from acme_bench import api

       registry.register_namespace("acme", api)
       _logger.debug("Registered col.acme namespace")

Declare it in ``pyproject.toml``::

   [project.entry-points."colosseum.plugins"]
   acme = "acme_bench:register"

After ``pip install -e .`` (or a wheel install) in the same environment as
``colosseum-core``, the namespace becomes ``col.acme``. Source checkouts alone do
not provide entry-point metadata.

The entry-point **key** is metadata only. The runtime namespace is the string passed
to ``register_namespace``. Duplicate namespaces or config sections raise
``PluginRegistrationError``. A failing ``register()`` also fails fast at load time.

Reserved namespaces (do not register): ``equipment``, ``shared``, ``io``, ``host``,
``messaging``.

Layer 1 — Evidence decorators
-----------------------------

Use ``command``, ``measurement``, and ``verification`` from ``colosseum.decorators``
when you need recorded pass/fail evidence. See :doc:`measurements_verifications`.

``register_namespace`` sets the evidence domain to the namespace name when the
package has not already set ``__colosseum_domain__``. Override that attribute on the
package (or function) when the domain should differ.

Layer 2 — Bench configuration
-----------------------------

Only plugins that own TOML sections need this. See :doc:`configuration` for load
behavior. Each ``ConfigSectionSpec`` is one table type:

* exactly one ``dotted_path``
* exactly one ``id_field`` (integer, unique per section)
* any number of ``required_keys`` and ``optional_keys`` (including none)

Register another spec for another dotted path. Then document matching rows::

   from colosseum.config.sections import ConfigSectionSpec

   registry.register_config_section(
       ConfigSectionSpec(
           dotted_path="acme.device",
           id_field="device_id",
           required_keys=("serial",),
           optional_keys=("label",),
       )
   )

End-user bench TOML::

   [[acme.device]]
   device_id = 1
   serial = "DUT-001"
   # label = "optional"

Unknown keys produce warnings. Missing required keys raise when the row is loaded
with ``require_item``. Registered section keys appear in the generated bench
configuration reference when the plugin is installed during a core docs build.

Layer 3 — Resources and extras
------------------------------

Optional registry hooks:

* ``registry.register_config_validator(dotted_path, fn)`` — return warning strings.
* ``registry.register_shutdown(callable)`` — cleanup on ``col.endex()`` (LIFO order).

Connection helpers (config lookup, ``resource_cache``) are ordinary module functions,
not a framework decorator. The template demo reads config inline; first-party plugins
such as messaging and equipment show cached-resource patterns.

Logging
-------

Plugins log through ``colosseum.logging.get_logger`` with a name under the
``colosseum`` tree. ``setup_logging`` attaches the run file handler to the
``colosseum`` logger, so only that subtree is written to ``debug.log``::

   from colosseum.logging import get_logger

   _logger = get_logger("colosseum.acme")

Use ``colosseum.<namespace>`` to match the registered namespace (``col.acme`` →
``colosseum.acme``). Child loggers such as ``colosseum.acme.api`` are fine. Names
like ``acme`` or ``acme_bench`` never reach ``debug.log``.

The file handler records DEBUG and above. Console output, when enabled, defaults
to INFO. Decorators already record command, measurement, and verification
pass/fail; do not duplicate that at INFO.

Documentation
-------------

Plugins document themselves (README and any project-local docs). Register
``colosseum.plugins`` only.
