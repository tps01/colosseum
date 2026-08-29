# Testing

Core tests are standalone and never require sibling plugin repositories.

```sh
python scripts/run_tests.py
python scripts/run_static.py
python tests/regression/run_soak_sim.py --count 5
python tests/regression/run_docgen_check.py --skip-pdf
python -m build
```

The pytest tiers are:

- `tests/unit`: isolated behavior and data contracts
- `tests/integration`: runtime, configuration, plugin registration, and evidence lifecycle
- `tests/e2e`: CLI and suite subprocess behavior (black-box framework specification)

**E2E behavioral spec:** [`e2e-spec.md`](e2e-spec.md) lists requirement IDs, acceptance
criteria, fixtures, and test names. Use it for test-driven development or
reimplementation of the framework contract.

`tests/support/core_api.py` is the intentionally small decorated API used for runtime
coverage without installing a plugin. Plugin repositories own their hardware, protocol,
simulation, and integration suites.

Use `scripts/profile_tests.py` or `scripts/profile_run.py` for local profiling.

```sh
pytest tests/e2e -v
python scripts/profile_tests.py --tier e2e
```
