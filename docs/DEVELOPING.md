# Developing Colosseum Core

Core is independently buildable and testable. Sibling plugin checkouts are not
required.

This page is **Part 1** (setup and checks). **Part 2** (runtime execution and
plugin authoring) is later on this page and in the Sphinx PDF manual.

## Part 1: Setup

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

The PDF is the primary Sphinx manual and needs `latexmk`. CI builds HTML on
every change as a backup; release automation builds the PDF.

## Boundaries

- Keep hardware, transport, host, network, and protocol behavior in plugins.
- Test plugin discovery with test doubles; do not install sibling repositories
  in core CI.
- Keep plugin packages responsible for their own device examples, simulation
  fixtures, and
  integration tests.
- Core may document the plugin specification but must not hard-code first-party
  plugin modules.

## Part 2: Runtime execution and plugins

Sphinx PDF Part 2 (**Developing Colosseum**) is the primary write-up:

- [Runtime execution](sphinx/source/guides/runtime_execution.rst)
- [Plugins and extensions](sphinx/source/guides/plugins.rst)
- [Glossary](sphinx/source/guides/glossary.rst) (PDF appendix)

Build the PDF with `python scripts/docgen/build_all.py` (`latexmk` required).
HTML is the same sources: `python scripts/docgen/build_all.py --skip-pdf`.

## Releases

Release tags use `v<version>` and must match `project.version` in
`pyproject.toml`.
The release workflow publishes the core wheel, sdist, and core documentation.
