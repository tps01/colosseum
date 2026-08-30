# Sphinx user documentation

Hand-written guides: `source/guides/`

Build the full site from the repository root:

```bash
pip install -e .
python scripts/docgen/build_all.py
```

Open `build/docgen/site/html/index.html`. PDF:
`build/docgen/site/latex/colosseum.pdf` (requires `latexmk` and LaTeX; use
`python scripts/docgen/build_all.py --skip-pdf` for HTML only).

See [scripts/docgen/README.md](../../scripts/docgen/README.md) for the build
pipeline.
