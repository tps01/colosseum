Plugins and extensions
======================

Plugins are separate Python distributions discovered from setuptools entry points.
The copy-ready template is under ``examples/plugins/colosseum_template``.

Runtime registration
--------------------

A plugin exposes a registration callable::

   from colosseum.config.sections import ConfigSectionSpec
   from colosseum.logging import get_logger

   _logger = get_logger("colosseum.acme")

   def register(registry):
       from acme_plugin import api

       registry.register_namespace("acme", api)
       _logger.debug("Registered col.acme namespace")
       registry.register_config_section(
           ConfigSectionSpec(
               dotted_path="acme.device",
               id_field="device_id",
               required_keys=("resource",),
           )
       )

Declare it in ``pyproject.toml``::

   [project.entry-points."colosseum.plugins"]
   acme = "acme_plugin:register"

The namespace becomes ``col.acme`` after the distribution is installed. Duplicate
namespaces or config sections raise ``PluginRegistrationError``.

Logging
-------

Plugins log through ``colosseum.logging.get_logger`` with a name under the
``colosseum`` tree. ``setup_logging`` attaches the run file handler to the
``colosseum`` logger, so only that subtree is written to ``debug.log``::

   from colosseum.logging import get_logger

   _logger = get_logger("colosseum.template")

Use ``colosseum.<namespace>`` to match the registered namespace (``col.template``
→ ``colosseum.template``). Child loggers such as ``colosseum.template.api`` are
fine. Names like ``template`` or ``colosseum_template`` never reach ``debug.log``.

The file handler records DEBUG and above. Console output, when enabled, defaults
to INFO, so plugin ``_logger.debug(...)`` is for internals that belong in the run
artifact without flooding stdout. Decorators already record command, measurement,
and verification pass/fail; do not duplicate that at INFO.

The copy-ready template under ``examples/plugins/colosseum_template`` shows this
pattern in ``api.py``, ``__init__.py``, ``connections.py``, and ``validators.py``.
First-party plugins (host, shared, messaging, equipment) use the same names:
``colosseum.host``, ``colosseum.shared``, ``colosseum.messaging``,
``colosseum.equipment``, and ``colosseum.io``.

Decorated APIs
--------------

Plugin API functions use ``command``, ``measurement``, and ``verification`` from
``colosseum.decorators``. Set ``__colosseum_domain__`` on the package when evidence
should use a domain other than ``core``.

Shutdown hooks registered with ``registry.register_shutdown`` run in reverse order when
``col.endex()`` finalizes the runtime.

Documentation
-------------

Plugins document themselves (README and any project-local docs). Register
``colosseum.plugins`` only. When your plugin is installed during a core docs
build, its ``ConfigSectionSpec`` keys appear in the generated bench
configuration reference.

Source checkouts do not provide entry-point metadata. Use ``pip install -e .`` while
developing a plugin.
