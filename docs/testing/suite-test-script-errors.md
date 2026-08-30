# Suite behavior when a test script raises

## Output model

Each script in a suite runs in its own child folder under the suite container.
Only
**test** slot results determine suite pass/fail. Setup, `between_tests`, and
teardown
slots keep their own logs and optional SQLite evidence but do not affect the
suite
outcome unless `rip_cord = true`.

## Default behavior (`fail_fast = false`, `rip_cord = false`)

When a script in the suite **`tests`** list raises an uncaught exception:

1. The runner logs a `script_fail:...` event in that test slot's database.
2. The test slot is finalized as FAIL; later tests and teardown still run.
3. The suite container summary reports FAIL if any test slot failed.

Therefore a suite exits **`1`** when a test script crashes without recording
verifications.

This is covered by
`tests/integration/test_suite_runner.py::test_test_script_exception_fails_suite_without_verification`.

When a test entry uses **`repeat_count`** or **`repeat_for`**, a failed
iteration does
not stop later iterations of that entry unless `fail_fast = true`. Failures
accumulate
across the soak window.

Supporting-script failures (setup, `between_tests`, teardown) are logged in
their slot
folders and the suite **continues** unless `rip_cord = true`.

## Rationale

The default preserves suite throughput and teardown execution. Test-script
failures still
fail the suite because the script did not complete its evidence path. See
[docs/scope.md](../scope.md).

## `fail_fast = true`

When continuing after a test failure would be dangerous, set in the suite TOML:

```toml
fail_fast = true
```

Then the runner stops remaining **test** iterations after:

- an uncaught test script exception / early exit, or
- a required verification or command FAIL/ERROR after a test returns

Teardown still runs. Optional failures do not stop the suite.

`between_tests` failures do not honor `fail_fast`; use `rip_cord` when
between-script
failures must abort the suite.

## `rip_cord = true`

When any script-slot failure must abort immediately:

```toml
rip_cord = true
```

The runner skips remaining scheduled setup/tests/between slots, runs teardown,
and fails
the suite when **any** slot raises, exits non-zero, or records a required
FAIL/ERROR
(including supporting scripts that use Colosseum decorators).

Covered by `tests/integration/test_suite_runner.py` fail-fast, rip-cord, and
repeat cases.
