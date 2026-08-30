# Developing Colosseum Core

Core is independently buildable and testable. Sibling plugin checkouts are not
required.

## Setup

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e .
```

That single editable install includes runtime, test, static-analysis, and docs
tooling.

## Checks

```sh
python scripts/run_tests.py
python scripts/run_static.py
python tests/regression/run_soak_sim.py --count 5
python tests/regression/run_docgen_check.py --skip-pdf
python -m build
```

The PDF documentation path additionally needs `latexmk`; CI runs the HTML build
on every
change and release automation builds the PDF.

## Boundaries

- Keep hardware, transport, host, network, and protocol behavior in plugins.
- Test plugin discovery with test doubles; do not install sibling repositories
  in core CI.
- Keep plugin packages responsible for their own device examples, simulation
  fixtures, and
  integration tests.
- Core may document the plugin specification but must not hard-code first-party
  plugin modules.

## Releases

Release tags use `v<version>` and must match `project.version` in
`pyproject.toml`.
The release workflow publishes the core wheel, sdist, and core documentation.
