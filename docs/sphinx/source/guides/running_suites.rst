Running suites
==============

Suites are TOML files whose script paths are relative to the suite file::

   name = "smoke"
   setup = ["setup/prepare.py"]
   tests = ["tests/check_device.py"]
   teardown = ["teardown/cleanup.py"]
   # fail_fast = true   # optional: stop remaining tests after a failure

Run a suite with::

   colosseum run-suite suites/smoke.toml --config bench.toml

Setup, test, and teardown scripts share one runtime and output directory. A setup failure
skips tests but still runs teardown.

By default (``fail_fast = false``), a test script crash or required FAIL/ERROR does not
prevent later tests or teardown from running. Set ``fail_fast = true`` when continuing
after a failure would be unsafe: remaining tests are skipped, but teardown still runs.
Optional verification failures never trigger fail-fast.
