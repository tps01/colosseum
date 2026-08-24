Measurements, commands, and verifications
==========================================

Core records decorated API calls in ``execution.sqlite`` and ``debug.log``.
Plugin internals should use ``colosseum.logging.get_logger`` with
``colosseum.<namespace>`` (see :doc:`plugins`); those DEBUG lines land in the
same ``debug.log`` and are distinct from decorator pass/fail records.

Commands
--------

``@command`` records setup and action calls. When a required command raises, Colosseum
records an ERROR row and event, then re-raises so remaining script steps do not run.
The runner still calls ``col.endex()`` to write the FAIL result. ``optional=True``
records the ERROR without failing the run or aborting the script.

Measurements
------------

``@measurement`` records a returned value under a required ``key``. Keys are unique for
the same domain, command, and row index. Use ``multi_row=True`` for indexed series.

Verifications
-------------

``@verification`` records ``PASS``, ``FAIL``, or ``ERROR``. Look up prior
measurements in the verifier body (for example
``get_context().db.get_measurement(...)``) and return
``missing_measurement_result`` when evidence is absent.

Unlike commands, verification exceptions become ``VerificationResult(status="ERROR")``
and do not abort the script. Optional verifications may fail without failing the
aggregate result.

Domains
-------

Evidence is stored under a domain string. Resolution order:

1. Function-level ``__colosseum_domain__`` override.
2. Package (or parent package) ``__colosseum_domain__``.
3. Default: when ``register_namespace(name, module)`` runs, core sets the package
   domain to ``name`` if none is already set. Otherwise undecorated / unregistered
   APIs fall back to ``core``.

Third-party plugins usually get domain ``==`` namespace automatically from
``register_namespace``. Set ``__colosseum_domain__`` explicitly when they should differ.
