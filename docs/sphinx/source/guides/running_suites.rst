Running suites
==============

Suites are TOML files whose script paths are relative to the suite file::

   name = "smoke"
   setup = ["setup/prepare.py"]
   tests = ["tests/check_device.py"]
   between_tests = ["scripts/delay.py"]
   teardown = ["teardown/cleanup.py"]
   # fail_fast = true   # optional: stop remaining test iterations after a failure
   # rip_cord = true    # optional: abort to teardown on any script-slot failure

Each entry in ``tests`` is either a path string (one run) or an inline table with
``path`` and optional repeat settings:

* ``repeat_count = N``: run the script exactly ``N`` times (``N >= 1``).
* ``repeat_for = "24h"``: run until the duration elapses (always at least one run).
  Use suffixes ``s``, ``m``, ``h``, or ``d`` (for example ``30s``, ``90m``, ``24h``).
  ``repeat_count`` and ``repeat_for`` are mutually exclusive.

Optional ``between_tests`` scripts run **between** test executions, including between
repeat iterations of the same test, but not before the first test or after the final
iteration (teardown follows immediately).

Run a suite with::

   colosseum run-suite suites/smoke.toml --config config/config.toml

Pass ``--metadata config/metadata.yaml`` when test slots should include metadata identity
fields in their JSON test reports. Without metadata, each test slot still writes a
best-effort report using runtime defaults.

Suite CLI options
-----------------

Suites accept the shared path and config flags documented in :doc:`running_tests`
(``-i``, ``-o``, ``-g``, ``-m``, ``-d``, ``--no-artifacts``). Suites also accept
``-p/--procedure``, which runs **test** slots in procedure mode (commands and
measurements only; verifications are skipped). Setup, ``between_tests``, and teardown
slots are unaffected.

Worked example: between two tests
---------------------------------

The suite below runs ``test_a.py``, then ``between.py``, then ``test_b.py``.
``between.py`` does **not** run before the first test or after the last.

**suites/between_two_tests.toml**::

   name = "demo_between_two_tests"

   tests = ["../scripts/test_a.py", "../scripts/test_b.py"]
   between_tests = ["../scripts/between.py"]

Each test script can be minimal. The runner provides an output directory through
``get_context().output_dir``:

**scripts/test_a.py**::

   def main() -> None:
       from colosseum.context import get_context

       ctx = get_context()
       path = ctx.output_dir / "invocations.txt"
       with path.open("a", encoding="utf-8") as handle:
           handle.write("test_a\n")

**scripts/between.py**::

   def main() -> None:
       from colosseum.context import get_context

       ctx = get_context()
       path = ctx.output_dir / "invocations.txt"
       with path.open("a", encoding="utf-8") as handle:
           handle.write("between\n")

Execution order: ``test_a`` slot, ``between`` slot, ``test_b`` slot. With
``repeat_count = 3`` on a single test, ``between_tests`` runs between each iteration.

Output layout
-------------

Each suite run creates a **container** directory under ``outputs/``::

   outputs/2026-08-24_180000_boot_soak-pass/
     summary.txt          # roll-up across test slots
     summary.json
     2026-08-24_180000_prepare/          # setup slot (no -pass/-fail suffix)
     2026-08-24_180001_boot_verify-pass/ # test slot (full artifacts + result suffix)
     2026-08-24_180030_sleep_30s/        # between_tests slot
     2026-08-24_180045_cleanup/          # teardown slot

Every script execution (setup, ``between_tests``, each test iteration, teardown) gets its
own child folder under the container. **Test** slots receive the same artifacts as a
standalone ``colosseum run`` (``debug.log``, ``execution.sqlite``, ``summary.txt``,
``wats_<datetime>_<script>.json``, and a ``-pass`` / ``-fail`` directory rename).
Supporting slots (setup, ``between_tests``, teardown) keep a timestamped folder without a
result suffix. They write ``debug.log`` and ``execution.sqlite`` only. They do not write
``summary.txt``, ``summary.json``, or the JSON test report.

Suite pass/fail is determined **only from test script slots**. Setup, ``between_tests``,
and teardown outcomes are recorded in their slot folders but do not change the suite
result unless ``rip_cord = true``.

During a suite run, ``col.endex()`` finalizes the **current script slot** and returns
control to the runner (it does not exit the process). The runner finalizes each slot
automatically when a script returns without calling ``endex()``.

``fail_fast`` and ``rip_cord``
------------------------------

By default (``fail_fast = false``), a failed **test** iteration does not prevent later
test iterations or teardown. Set ``fail_fast = true`` to skip remaining scheduled test
runs after a test-slot failure. Optional verification failures never trigger fail-fast.

Set ``rip_cord = true`` when any script-slot failure must abort the suite immediately
(exception, non-zero exit, or required verification/command FAIL/ERROR in that slot).
The runner skips remaining setup/tests/between slots, runs teardown, and fails the suite.

Soak-style suites accumulate failures across repeat iterations; the suite container
summary and exit code reflect whether any test slot failed.
