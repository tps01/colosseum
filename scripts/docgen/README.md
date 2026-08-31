# Documentation generation

The PDF is the primary Sphinx manual. HTML is a backup of the same sources.

Full build (requires `latexmk`):

```sh
python scripts/docgen/build_all.py
```

HTML only:

```sh
python scripts/docgen/build_all.py --skip-pdf
```

The pipeline copies handwritten guides from `docs/sphinx/source/` and invokes
Sphinx. Plugins document themselves (README or project-local docs); they do not
join this build.
