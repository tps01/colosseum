# Agent guide

Read `RULES.md` before changing dependencies. Do not commit, push, merge, or tag unless
the user explicitly requests it.

## Scope

`colosseum-core` owns the runtime only:

- decorators and result aggregation
- configuration and plugin contracts
- test/suite runners and optional GUI
- SQLite evidence, output paths, artifacts, logging, and summaries
- user documentation (guides + generated config reference)

Device drivers, transports, SSH, host inspection, and bench-specific APIs belong in plugins.
Core tests must run without sibling repositories or first-party plugins installed.

## Change discipline

- Keep changes focused and reviewable.
- Preserve public plugin interfaces unless an intentional compatibility change is requested.
- Do not add integration dependencies to core for plugin-owned behavior.
- Keep examples generic; plugin-specific examples and fixtures live with that plugin.
- Update relevant docs and tests with behavior changes.

## Commands

```sh
python -m pip install -r requirements-dev.txt
python scripts/run_tests.py
python scripts/run_static.py
python tests/regression/run_soak_sim.py --count 5
python tests/regression/run_docgen_check.py --skip-pdf
python -m build
```

PDF documentation additionally requires `latexmk`.

## Public behavior

- User import: `import colosseum as col`.
- Plugins register through `colosseum.plugins`.
- Plugin namespaces resolve dynamically as `col.<namespace>`.
- End test scripts with `col.endex()` to finalize evidence and exit consistently.
- Public APIs and maintainer scripts use Sphinx field-list docstrings.
