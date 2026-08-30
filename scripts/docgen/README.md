# Documentation generation

Build standalone core HTML documentation:

```sh
python scripts/docgen/build_all.py --skip-pdf
```

The full build additionally requires `latexmk`:

```sh
python scripts/docgen/build_all.py
```

The pipeline copies handwritten guides from `docs/sphinx/source/` and invokes
Sphinx. Plugins document themselves (README or project-local docs); they do not
join this build.
