#!/usr/bin/env python3
"""
Build Colosseum core documentation: handwritten guides + config reference.

1. Copy ``docs/sphinx/source/`` into ``build/docgen/site/source/``
2. Generate ``guides/bench_config_reference.rst`` from installed plugins
3. Run ``sphinx-build`` for HTML and optionally LaTeX/PDF
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from _bootstrap import bootstrap

bootstrap()

_scripts_dir = Path(__file__).resolve().parents[1]
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from build_config_reference import build_config_reference_rst  # noqa: E402
from build_pdf import build_pdf  # noqa: E402

from ci.timing import ci_phase  # noqa: E402


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_docgen_root(docgen_root: Path | None) -> Path:
    return docgen_root or (_repo_root() / "build" / "docgen")


def build_staged_site(
    *,
    docgen_root: Path | None = None,
    clean: bool = False,
) -> Path:
    """Copy guides and generate the bench config reference into the site source tree.

    :param docgen_root: Staging root (default: ``build/docgen`` under repo root).
    :type docgen_root: Path | None, optional
    :param clean: When ``True``, remove the site root before rebuilding.
    :type clean: bool, optional

    :returns: Site root directory (contains ``source/`` for ``sphinx-build``).
    :rtype: Path
    """
    repo_root = _repo_root()
    docgen_root = _default_docgen_root(docgen_root)
    site_root = docgen_root / "site"
    site_source = site_root / "source"
    guides_root = repo_root / "docs" / "sphinx" / "source"

    if not guides_root.is_dir():
        raise SystemExit(f"Sphinx source not found at {guides_root}")

    with ci_phase("staging"):
        if clean and site_root.exists():
            shutil.rmtree(site_root)
        elif site_source.exists():
            shutil.rmtree(site_source)

        shutil.copytree(guides_root, site_source)

        print("Building bench config reference")
        build_config_reference_rst(
            output_path=site_source / "guides" / "bench_config_reference.rst"
        )

    return site_root


def build_sphinx_html(*, site_source: Path, html_dir: Path, repo_root: Path) -> Path:
    """Run ``sphinx-build -b html`` and return the index path.

    :param site_source: Staged Sphinx source tree.
    :type site_source: Path
    :param html_dir: HTML output directory.
    :type html_dir: Path
    :param repo_root: Repository root (sphinx working directory).
    :type repo_root: Path

    :returns: Path to ``index.html``.
    :rtype: Path
    """
    html_dir.mkdir(parents=True, exist_ok=True)
    with ci_phase("html"):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "sphinx",
                "-b",
                "html",
                str(site_source),
                str(html_dir),
            ],
            cwd=repo_root,
            check=True,
        )
    return html_dir / "index.html"


def build_docs(
    *,
    docgen_root: Path | None = None,
    clean: bool = False,
    skip_html: bool = False,
    skip_pdf: bool = False,
) -> tuple[Path | None, Path | None]:
    """Stage documentation and build HTML and/or PDF outputs.

    :param docgen_root: Staging root (default: ``build/docgen``).
    :type docgen_root: Path | None, optional
    :param clean: When ``True``, remove staged outputs before rebuilding.
    :type clean: bool, optional
    :param skip_html: When ``True``, skip the HTML ``sphinx-build`` step.
    :type skip_html: bool, optional
    :param skip_pdf: When ``True``, skip LaTeX/PDF generation.
    :type skip_pdf: bool, optional

    :returns: ``(html_index, pdf_path)``; either element may be ``None`` when skipped.
    :rtype: tuple[Path | None, Path | None]
    """
    repo_root = _repo_root()
    site_root = build_staged_site(docgen_root=docgen_root, clean=clean)
    site_source = site_root / "source"
    html_index: Path | None = None
    pdf_path: Path | None = None

    if not skip_html:
        html_dir = site_root / "html"
        print("Running sphinx-build (html)...")
        html_index = build_sphinx_html(
            site_source=site_source,
            html_dir=html_dir,
            repo_root=repo_root,
        )
        print(f"HTML output: {html_index}")

    if not skip_pdf:
        latex_dir = site_root / "latex"
        print("Running sphinx-build (latex) and latexmk...")
        with ci_phase("pdf"):
            pdf_path = build_pdf(
                site_source=site_source,
                latex_dir=latex_dir,
                repo_root=repo_root,
            )
        print(f"PDF output: {pdf_path}")

    return html_index, pdf_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the documentation build pipeline.

    :param argv: Optional argument vector (defaults to ``sys.argv[1:]``).
    :type argv: list[str] | None, optional

    :returns: Process exit code (``0`` on success).
    :rtype: int
    """
    parser = argparse.ArgumentParser(description="Build Colosseum Sphinx documentation")
    parser.add_argument("--docgen-root", type=Path, help="Default: build/docgen")
    parser.add_argument("--clean", action="store_true", help="Remove staged outputs before build")
    parser.add_argument(
        "--skip-html", action="store_true", help="Build PDF only (still runs staging)"
    )
    parser.add_argument(
        "--skip-pdf", action="store_true", help="Build HTML only (no LaTeX required)"
    )
    args = parser.parse_args(argv)

    if args.skip_html and args.skip_pdf:
        parser.error("Cannot use both --skip-html and --skip-pdf")

    build_docs(
        docgen_root=args.docgen_root,
        clean=args.clean,
        skip_html=args.skip_html,
        skip_pdf=args.skip_pdf,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
