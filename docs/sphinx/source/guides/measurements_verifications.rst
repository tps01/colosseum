Measurements, commands, and verifications
==========================================

Core records decorated API calls in ``execution.sqlite`` and ``debug.log``.
Plugin internals should use ``colosseum.logging.get_logger`` with
``colosseum.<namespace>`` (see :doc:`plugins`); those DEBUG lines land in the
same ``debug.log`` and are distinct from decorator pass/fail records.

Commands
--------

``@command`` records setup and action calls. A required command failure contributes to
the final run status. ``optional=True`` records a failure without failing the run.

Measurements
------------

``@measurement`` records a returned value under a required ``key``. Keys are unique for
the same domain, command, and row index. Use ``multi_row=True`` for indexed series.

Verifications
-------------

``@verification`` records ``PASS``, ``FAIL``, or ``ERROR``. Look up prior
measurements in the verifier body (for example
``require_context().db.get_measurement(...)``) and return
``missing_measurement_result`` when evidence is absent.

Optional verifications may fail without failing the aggregate result.

Domains
-------

The defining package may set ``__colosseum_domain__`` to choose the SQLite evidence
domain. A function-level ``__colosseum_domain__`` override takes precedence. APIs without
an override use ``core``.
