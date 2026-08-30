Running test cases
==================

Direct Python execution loads configuration and calls ``col.endex()`` from the script.
The CLI initializes and finalizes the runtime around ``main()``::

   colosseum run my_test.py -g config.toml -m metadata.yaml

The CLI does not execute the script's ``if __name__ == "__main__"`` block.

See :doc:`writing_test_scripts` for a complete script with matching config TOML and
metadata YAML.

Output directories
------------------

Normal runs create ``debug.log``, ``execution.sqlite``, ``summary.txt``, and
``summary.json`` beneath ``outputs/<timestamp>_<name>-pass/`` or
``outputs/<timestamp>_<name>-fail/``. A JSON test report
``wats_<datetime>_<script>.json`` (WATS WSJF format) is written in the same directory.
Metadata enriches identity fields when configured; otherwise Colosseum uses runtime
defaults.

During execution, before the final result is known, the active directory is named
``outputs/<timestamp>_<name>/``. After ``col.endex()``, the directory is renamed with
``-pass`` or ``-fail``.

Use ``--metadata PATH`` (or ``col.config.load_metadata``) with ``--config`` when
both config TOML and metadata YAML are required.

Use ``--no-artifacts``, ``load_config(..., no_artifacts=True)``, or
``COLOSSEUM_NO_ARTIFACTS=1`` for console logging and in-memory SQLite without files.

Pass ``-d`` or ``--debug`` to include DEBUG messages on stdout. The persisted log always
includes DEBUG messages.

CLI options
-----------

Shared path and config flags for ``colosseum run`` and ``colosseum run-suite``:

- ``-i/--input-dir PATH`` — base directory for the positional script or suite path
- ``-o/--output-dir PATH`` — custom output root for timestamped run folders (default:
  ``cwd/outputs``)
- ``-g/--config PATH`` — config TOML (legacy short form)
- ``-m/--metadata PATH`` — metadata YAML (short form)
- ``-d/--debug`` — include DEBUG logs on stdout
- ``--no-artifacts`` — in-memory SQLite and console logging only

``colosseum run`` additionally supports:

- ``-c/--command SPEC`` — invoke a plugin ``@command`` (``namespace.function,key=val,...``);
  repeatable; may be used without a script path
- ``-p/--procedure`` — run commands and measurements; skip verifications
- ``-u/--use-previous-output PATH`` — import prior measurements/commands from a completed
  run directory and re-run verifications only (mutually exclusive with ``-p``)
- ``--show-faults`` — opt-in ``faulthandler`` crash dumps for this run

Examples::

   colosseum run scripts/my_test.py -i scripts -g config/config.toml -m config/metadata.yaml
   colosseum run -o D:/test_runs -c template.arm_device,device_id=1 -g config/config.toml
   colosseum run scripts/my_test.py -p -g config/config.toml
   colosseum run scripts/my_test.py -u outputs/2026-01-01_120000_my_test-pass -g config/config.toml

Standalone ``-c`` runs allocate a normal output directory and record command evidence
without executing a test script. Combine ``-c`` with a script path to run plugin commands
and the script in one process and one output directory.

See :doc:`running_suites` for suite-specific flags (including ``-p`` on test slots).
