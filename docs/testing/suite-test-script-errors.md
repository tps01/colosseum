# Suite behavior when a test script raises

## Default behavior (`fail_fast = false`)

When a script in the suite **`tests`** list raises an uncaught exception:

1. The runner logs a `script_fail:...` event and continues with remaining tests.
2. Teardown still runs.
3. The aggregate result is marked failed through a suite error.

Therefore a suite exits **`1`** when a test script crashes without recording verifications.

This is covered by `tests/integration/test_suite_runner.py::test_test_script_exception_fails_suite_without_verification`.

## Rationale

The default preserves suite throughput and teardown execution, but an uncaught test exception is still a failed run because the script did not complete its evidence path. See [docs/scope.md](../scope.md).

## `fail_fast = true`

When continuing after a failure would be dangerous, set in the suite TOML:

```toml
fail_fast = true
```

Then the runner stops remaining tests after:

- an uncaught test script exception / early exit, or
- a required verification or command FAIL/ERROR after a test returns

Teardown still runs. Optional failures do not stop the suite.

Covered by `tests/integration/test_suite_runner.py` fail-fast cases.
