Running test cases
==================

Direct Python execution loads configuration and calls ``col.endex()`` from the script.
The CLI initializes and finalizes the runtime around ``main()``::

   colosseum run my_test.py --config bench.toml --metadata metadata.yaml

The CLI does not execute the script's ``if __name__ == "__main__"`` block.

See :doc:`writing_test_scripts` for a complete script with matching bench TOML and
metadata YAML.

Output directories
------------------

Normal runs create ``debug.log``, ``execution.sqlite``, ``summary.txt``, and
``summary.json`` beneath ``outputs/<timestamp>_<name>-pass/`` or
``outputs/<timestamp>_<name>-fail/``. A WATS report
``wats_<datetime>_<script>.json`` is written in the same directory. Metadata enriches
the report when configured; otherwise Colosseum exports a best-effort WATS file using
runtime defaults.

During execution, before the final result is known, the active directory is named
``outputs/<timestamp>_<name>/``. After ``col.endex()``, the directory is renamed with
``-pass`` or ``-fail``.

Use ``--metadata PATH`` (or ``col.config.load_metadata``) with ``--config`` when
both bench TOML and metadata YAML are required.

Use ``--no-artifacts``, ``load_config(..., no_artifacts=True)``, or
``COLOSSEUM_NO_ARTIFACTS=1`` for console logging and in-memory SQLite without files.

Pass ``-d`` or ``--debug`` to include DEBUG messages on stdout. The persisted log always
includes DEBUG messages.
