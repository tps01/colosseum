Output artifacts
================

Each completed test run writes evidence under ``outputs/``. See :doc:`running_tests`
for directory naming and :doc:`writing_test_scripts` for a full example run.

.. list-table::
   :header-rows: 1

   * - File
     - Description
   * - ``debug.log``
     - Run header and execution log. Lines use ``%(name)s`` (for example
       ``[colosseum.template]``). Plugin code must call
       ``colosseum.logging.get_logger`` with ``colosseum.<namespace>`` so
       DEBUG records reach this file (see :doc:`plugins`).
   * - ``execution.sqlite``
     - Measurements, verifications, events, metadata, and registered artifacts
   * - ``summary.txt``
     - End-of-run human summary (written by ``col.endex()``)
   * - ``summary.json``
     - End-of-run machine-readable summary (written by ``col.endex()``)
   * - ``wats_<datetime>_<script>.json``
     - WATS WSJF test report. Written on every normal run. Metadata enriches identity
       fields when configured; otherwise Colosseum uses runtime defaults.

WATS export
-----------

WATS JSON is always written when artifacts are enabled. You do not need a metadata file.

When metadata is configured (bench TOML ``[colosseum.metadata]`` or YAML
``test_metadata``), identity fields such as ``location``, ``process_code``, and
``uut`` populate the report. Optional ``wats_folder`` copies the file to an absolute
path after finalize.

The filename embeds a UTC timestamp and the script stem, for example
``wats_20260827T233344_my_test.json``.

The output directory is created on first log or database write. Suite runs use the suite
``name`` as the directory stem. Completed output directories are renamed with the final
result, for example ``outputs/<timestamp>_<name>-pass/`` or
``outputs/<timestamp>_<name>-fail/``. Disable persisted output with ``--no-artifacts``,
``load_config(..., no_artifacts=True)``, or ``COLOSSEUM_NO_ARTIFACTS=1`` (see
:doc:`running_tests`).

Plugin-generated files (for example spectrum trace CSV, IQ capture binaries, screenshots)
are written under the same output directory. Equipment APIs register them in the
``artifacts`` SQLite table via ``register_artifact``. RF trace files from
``col.equipment.speca.save_trace_data`` typically live at ``traces/<name>.csv`` relative
to the run directory.

Use ``col.database.read_verifications`` for inspection only; do not use read helpers to
decide pass/fail (use ``col.endex()``). For completed runs, use
``colosseum.database.read_from_path.read_from_path(...)`` to inspect an
``execution.sqlite`` file without an active runtime.
