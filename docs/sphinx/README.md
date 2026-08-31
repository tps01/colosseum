# Sphinx documentation

The **PDF** (`colosseum.pdf`) is the primary manual. HTML is the same sources
for browsing when LaTeX is not available.

Hand-written guides: `source/guides/`

Build from the repository root (`latexmk` required for PDF):

```bash
pip install -e .
python scripts/docgen/build_all.py
```

PDF: `build/docgen/site/latex/colosseum.pdf`

- Part 1 - **Using Colosseum** (operator guides)
- Part 2 - **Developing Colosseum** (runtime execution and plugin authoring)
- Appendix - glossary

HTML backup (`python scripts/docgen/build_all.py --skip-pdf`):
`build/docgen/site/html/index.html`.

See [scripts/docgen/README.md](../../scripts/docgen/README.md) for the build
pipeline.
