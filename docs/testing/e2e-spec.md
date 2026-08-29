# Colosseum core E2E specification

Black-box behavioral requirements for the Colosseum test framework. Each
requirement
maps to a subprocess test under `tests/e2e/` and can be used for test-driven
reimplementation without reading source.

Tests use the built-in `core` evidence domain via `tests/support/core_api.py`.
No
plugins are installed.

Integration tests under `tests/integration/` mirror many suite behaviors
in-process
for faster feedback; this document is the user-facing CLI contract.

## Single run (`colosseum run`)

### E2E-RUN-01

**Behavior:** A passing test run writes the full artifact set and exits 0.

**Acceptance criteria:**

- Process exit code is 0.
- `outputs/<timestamp>_<name>-pass/` contains `debug.log`, `execution.sqlite`,
  `summary.txt`, `summary.json`, and `wats_<datetime>_<script>.json`.
- `run_metadata` records `overall_status=PASS` and `exit_code=0`.
- Stdout includes `Colosseum version:` and `Overall result: PASS`.

**Fixtures:** `tests/fixtures/scripts/optional_fail_test.py`,
`tests/fixtures/core.toml`

**Test:** `test_run_cli.py::test_pass_run_writes_full_artifacts`

### E2E-RUN-02

**Behavior:** Optional verification FAIL does not change the exit code.

**Acceptance criteria:**

- Exit code 0 when required verifications pass and optional verification fails.
- Optional verification row has `status=FAIL` and `optional=1`.

**Fixtures:** `optional_fail_test.py`

**Test:** `test_run_cli.py::test_optional_verification_fail_exits_zero`

### E2E-RUN-03

**Behavior:** Required verification ERROR (missing measurement) exits 1.

**Acceptance criteria:**

- Exit code 1.
- Verification row has `status=ERROR` for the missing key.
- Output directory suffix is `-fail`.

**Fixtures:** `fail_required_verify.py`

**Test:** `test_run_cli.py::test_missing_measurement_exits_one`

### E2E-RUN-04

**Behavior:** Uncaught script exception exits 1; artifacts are still finalized.

**Acceptance criteria:**

- Exit code 1.
- `debug.log`, `execution.sqlite`, `summary.txt`, `summary.json` exist.
- `run_metadata.overall_status` is `FAIL`.

**Fixtures:** `crash_test.py`

**Test:** `test_run_cli.py::test_script_crash_exits_one_and_finalizes`

### E2E-RUN-05

**Behavior:** Required `@command` ERROR exits 1; command row is recorded.

**Acceptance criteria:**

- Exit code 1.
- `commands` table has `status=ERROR` for the failing command.
- Message indicates procedural failure.

**Fixtures:** `command_error_test.py`

**Test:** `test_run_cli.py::test_command_error_records_row_and_fails`

### E2E-RUN-06

**Behavior:** `--no-artifacts` skips persisted output.

**Acceptance criteria:**

- Exit code 0.
- No `outputs/` directory under the working directory.
- Stdout mentions no-artifacts mode.

**Fixtures:** `optional_fail_test.py`

**Test:** `test_run_cli.py::test_no_artifacts_skips_output_dir`

### E2E-RUN-07

**Behavior:** `--metadata` enriches the WATS report with YAML identity fields.

**Acceptance criteria:**

- WATS JSON contains `pn`, `rev`, `sn`, `processCode`, `location`, `purpose`
  from metadata.

**Fixtures:** `wats_smoke_test.py`, `metadata_example.yaml`

**Test:** `test_run_cli.py::test_metadata_enriches_wats_report`

### E2E-RUN-08

**Behavior:** During execution the output directory has no result suffix; after
finalize it is renamed with `-pass` or `-fail`.

**Acceptance criteria:**

- While `main()` runs, `output_dir.name` does not end with `-pass` or `-fail`.
- After finalize, the directory is renamed with the correct suffix.

**Fixtures:** `active_dir_probe.py`

**Test:** `test_run_cli.py::test_output_dir_renamed_after_finalize`

## Direct Python execution

### E2E-DIR-01

**Behavior:** `python script.py` with `load_config` and `col.endex()` matches
the CLI artifact contract.

**Acceptance criteria:**

- Exit code 0 for the optional-fail script.
- Same verification rows as CLI run for required and optional keys.

**Fixtures:** `optional_fail_test.py`

**Test:** `test_run_direct.py::test_direct_python_matches_cli_contract`

### E2E-DIR-02

**Behavior:** CLI invokes `main()` only; the runner finalizes even when
`col.endex()` is not called from the script.

**Acceptance criteria:**

- Script without `endex()` in code path still produces finalized artifacts when
  run via CLI.
- Exit code reflects verification outcomes.

**Fixtures:** `cli_no_endex_test.py`

**Test:** `test_run_direct.py::test_cli_finalizes_without_endex_in_script`

## Suite (`colosseum run-suite`)

### E2E-SUITE-01

**Behavior:** Happy suite runs setup, test, and teardown slots; container
passes.

**Acceptance criteria:**

- Exit code 0.
- Container directory ends with `-pass`.
- Container `summary.txt` reports overall PASS.
- Test slot has `execution.sqlite`.

**Fixtures:** `suites/happy.toml`

**Test:** `test_suite_cli.py::test_happy_suite_container_passes`

### E2E-SUITE-02

**Behavior:** Test slots get full artifacts; supporting slots get log and sqlite
only.

**Acceptance criteria:**

- Test slot: `summary.txt`, `summary.json`, WATS JSON present.
- Setup/teardown slot: `debug.log` and `execution.sqlite` only; no `summary.txt`
  or WATS.

**Fixtures:** `suites/happy.toml`

**Test:** `test_suite_cli.py::test_slot_artifact_sets`

### E2E-SUITE-03

**Behavior:** Setup failure does not fail the suite when `rip_cord` is false.

**Acceptance criteria:**

- Exit code 0.
- Test slot still runs.

**Fixtures:** `suites/setup_fail.toml`

**Test:** `test_suite_cli.py::test_setup_fail_exits_zero_without_rip_cord`

### E2E-SUITE-04

**Behavior:** Teardown failure does not fail the suite when tests pass.

**Acceptance criteria:**

- Exit code 0.
- Container ends with `-pass`.

**Fixtures:** `suites/teardown_fail.toml`

**Test:** `test_suite_cli.py::test_teardown_fail_does_not_fail_suite`

### E2E-SUITE-05

**Behavior:** Test script crash fails the suite.

**Acceptance criteria:**

- Exit code 1.
- Container ends with `-fail`.
- `script_fail` event in test slot database.

**Fixtures:** `suites/test_script_crash.toml`

**Test:** `test_suite_cli.py::test_test_script_crash_fails_suite`

### E2E-SUITE-06

**Behavior:** `fail_fast=true` skips remaining tests after a test-slot failure.

**Acceptance criteria:**

- Exit code 1.
- Second test script does not run.
- Failing slot has `fail_fast_stopped` metadata.

**Fixtures:** `suites/multi_test_fail_fast_crash.toml`

**Test:** `test_suite_cli.py::test_fail_fast_stops_remaining_tests`

### E2E-SUITE-07

**Behavior:** `rip_cord=true` aborts on setup failure, runs teardown, fails
suite.

**Acceptance criteria:**

- Exit code 1.
- Test script does not run.
- `rip_cord_triggered` in container summary JSON.

**Fixtures:** `suites/setup_fail_rip_cord.toml`

**Test:** `test_suite_cli.py::test_rip_cord_aborts_on_setup_failure`

### E2E-SUITE-08

**Behavior:** `between_tests` runs between test slots, not before the first or
after the last.

**Acceptance criteria:**

- Slot directories exist for test A, between, and test B in order.

**Fixtures:** `suites/between_two_tests.toml`

**Test:** `test_suite_cli.py::test_between_tests_runs_between_executions`

### E2E-SUITE-09

**Behavior:** `repeat_count` runs N iterations; `between_tests` runs between
iterations.

**Acceptance criteria:**

- N test slot folders for the repeated script.
- N-1 between slot folders.

**Fixtures:** `suites/repeat_count.toml`

**Test:** `test_suite_cli.py::test_repeat_count_runs_between_iterations`

### E2E-SUITE-10

**Behavior:** Suite `--metadata` propagates identity fields to test-slot WATS
files.

**Acceptance criteria:**

- WATS JSON in test slot contains metadata identity fields.

**Fixtures:** `suites/smoke.toml`, `metadata_example.yaml`

**Test:** `test_suite_cli.py::test_suite_metadata_propagates_to_wats`

## Configuration errors

### E2E-CFG-01

**Behavior:** Invalid bench TOML exits 1 before the suite runs.

**Acceptance criteria:**

- Exit code 1.
- No suite container created.

**Fixtures:** inline bad TOML, `suites/happy.toml`

**Test:** `test_suite_cli.py::test_bad_config_exits_one`

## WATS artifacts

### E2E-ART-WATS-01

**Behavior:** WATS JSON is written on every normal run with artifacts enabled.

**Acceptance criteria:**

- Exactly one `wats_*.json` file in the run directory.

**Fixtures:** `optional_fail_test.py`

**Test:** `test_wats_cli.py::test_wats_file_always_written`

### E2E-ART-WATS-02

**Behavior:** WATS filename matches `wats_<UTCdatetime>_<script_stem>.json`.

**Acceptance criteria:**

- Filename matches regex `wats_\d{8}T\d{6}_<stem>.json`.

**Fixtures:** `optional_fail_test.py`

**Test:** `test_wats_cli.py::test_wats_filename_pattern`

### E2E-ART-WATS-03

**Behavior:** Metadata YAML populates WATS identity fields.

**Acceptance criteria:**

- `pn`, `rev`, `sn`, `processCode`, `location`, `purpose` match metadata file.

**Fixtures:** `wats_smoke_test.py`, `metadata_example.yaml`

**Test:** `test_wats_cli.py::test_wats_metadata_identity_fields`

### E2E-ART-WATS-04

**Behavior:** Without metadata, best-effort WATS export still succeeds.

**Acceptance criteria:**

- WATS file exists with `type=T` and valid JSON structure.
- Identity fields may be empty strings.

**Fixtures:** `wats_best_effort_test.py`

**Test:** `test_wats_cli.py::test_wats_best_effort_without_metadata`
