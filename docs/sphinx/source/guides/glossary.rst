Glossary
========

Terms used in the runtime and in the user guides. See
:doc:`runtime_execution` for the execution walkthrough.

.. glossary::

   artifacts
      Files written for a completed run: ``debug.log``, ``execution.sqlite``,
      summaries, and the WATS JSON report. Disabled with ``--no-artifacts``.

   command
      A decorated plugin call that records a stimulus or setup step in the
      ``commands`` table. Distinct from a CLI subcommand such as
      ``colosseum run``.

   ConfigSectionSpec
      Plugin-owned declaration of one TOML table: dotted path, integer id
      field, and required/optional keys.

   ConfigStore
      Loaded config TOML on the :term:`RuntimeContext`: raw nested dict plus
      ID-indexed plugin sections.

   domain
      Evidence namespace string stored on each SQLite row (for example
      ``template`` or ``core``). Resolved from ``__colosseum_domain__`` or
      the registered plugin namespace.

   endex
      ``col.endex()``. Finalizes the active run or suite slot: scores
      outcomes, writes artifacts, and (for a single run) exits the process.

   evidence
      Persisted command, measurement, verification, and event rows for one
      run or slot. SQLite is the source of truth; summaries are projections.

   evidence key
      The ``key=`` argument that ties a measurement to later verifications
      (and often to a command). Unique per ``(domain, command, key)`` unless
      ``multi_row=True``.

   execution mode
      ``full`` (default), ``procedure`` (``-p``, skip verifications), or
      ``verify_only`` (``-u``, import prior measurements/commands and re-run
      verifications).

   fail_fast
      Suite TOML flag. After a failing **test** slot, skip remaining tests.
      Supporting slots are unaffected. See :doc:`running_suites`.

   measurement
      A decorated plugin call that stores a captured value under
      ``(domain, command, key)`` in the ``measurements`` table.

   namespace
      The string passed to ``register_namespace``. Scripts call
      ``col.<namespace>.*`` (for example ``col.template``).

   optional
      ``optional=True`` on a command or verification. FAIL/ERROR is recorded
      but does not change the aggregate exit code.

   plugin
      A separate Python distribution with a ``colosseum.plugins`` entry
      point. ``register(registry)`` exposes a namespace and optional config
      sections. See :doc:`plugins`.

   resource cache
      ``RuntimeContext.resource_cache``. Plugin-owned live objects
      (connections, sessions). Core calls ``.close()`` at shutdown when
      present; plugins may also register shutdown hooks.

   ResultAggregator
      In-memory list of command and verification outcomes. Required FAIL or
      ERROR (or a marked script error) produces exit code 1.

   rip_cord
      Suite TOML flag. Any script-slot failure skips remaining setup/tests
      and runs teardown; the suite fails. See :doc:`running_suites`.

   RuntimeContext
      Process-wide singleton for one run or suite: config, plugins, SQLite,
      aggregator, output path, and execution mode. Retrieved with
      ``get_context()``.

   slot
      One script execution inside a suite (setup, test, between_tests, or
      teardown). Each slot has its own SQLite file and nested output folder.

   suite container
      Timestamped directory that holds slot folders plus the suite roll-up
      ``summary.txt`` / ``summary.json``. Renamed ``-pass`` or ``-fail``
      after finalize.

   verification
      A decorated plugin call that records PASS, FAIL, or ERROR against prior
      evidence, usually by :term:`evidence key`.

   WATS
      JSON test report (WSJF format) written as
      ``wats_<UTC>_<script>.json`` on every normal run with artifacts
      enabled. Metadata YAML enriches identity fields when provided.
