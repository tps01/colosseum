# Agent guide

Read `RULES.md` before changing dependencies. Do not commit, push, merge, or tag
unless
the user explicitly requests it.

## Scope

`colosseum-core` owns the runtime only:

- decorators and result aggregation
- configuration and plugin specifications
- test/suite runners and optional GUI
- SQLite evidence, output paths, artifacts, logging, and summaries
- user documentation (guides + generated config reference)

Device drivers, transports, SSH, host inspection, and bench-specific APIs belong
in plugins.
Core tests must run without sibling repositories or first-party plugins
installed.

## Change discipline

- Keep changes focused and reviewable.
- Preserve public plugin interfaces unless an intentional compatibility change
  is requested.
- Do not add integration dependencies to core for plugin-owned behavior.
- Keep examples generic; plugin-specific examples and fixtures live with that
  plugin.
- Update relevant docs and tests with behavior changes.

### Footprint (required)

Follow the workspace **Minimizing footprint** section in the top-level
`AGENTS.md`.
Before implementation:

1. **Distill** - Write a 3–5 line pre-flight: goal, protected behavior, out of
  scope.
2. **Inventory** - Search for existing modules/helpers; merge or extend instead
  of duplicating.
3. **Delete first** - Prefer removing or consolidating code when the public
  specification allows.
   Protected behavior: decorators, CLI, suite scheduling, standard output
artifacts, and
   plugin entry points (see `docs/testing/e2e-spec.md` and user guides).

Core owns the **runtime only** (decorators, runners, evidence DB, summaries,
optional GUI).
If a helper is used by one plugin family, it belongs in that plugin (e.g.
`toml_write` in
equipment), not in core.

Do not add compatibility shims in core when callers can import a stable path or
hold a
local copy-out helper in the plugin repo.

## Commands

```sh
python -m pip install -e .
python scripts/run_tests.py
python scripts/run_static.py
python tests/regression/run_soak_sim.py --count 5
python tests/regression/run_soak_inprocess.py --repeat 50
python tests/regression/run_docgen_check.py --skip-pdf
python -m build
```

When finishing a development session, run cleanup (dry-run first):

```sh
python scripts/cleanup.py --dry-run
python scripts/cleanup.py
```

See workspace `AGENTS.md` (**Simulated annealing**, **End-of-development
cleanup**).

PDF documentation additionally requires `latexmk`.

## Public behavior

- User import: `import colosseum as col`.
- Plugins register through `colosseum.plugins`.
- Plugin namespaces resolve dynamically as `col.<namespace>`.
- End test scripts with `col.endex()` to finalize evidence and exit
  consistently.
- Public APIs and maintainer scripts use Sphinx field-list docstrings.
