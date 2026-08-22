# Documentation generation

Build standalone core HTML documentation:

```sh
python scripts/docgen/build_all.py --skip-pdf
```

The full build additionally requires `latexmk`:

```sh
python scripts/docgen/build_all.py
```

The pipeline copies handwritten guides from `docs/sphinx/source/`, generates the
bench configuration reference from installed plugins' `ConfigSectionSpec`
registrations, and invokes Sphinx. A core-only environment documents only core.

Plugins document themselves (README / their own docs). They do not join this
build. When a plugin is installed during a docs build, its config sections appear
in the generated bench configuration reference.
