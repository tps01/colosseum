#!/usr/bin/env python3
"""R-DOC-01: verify Sphinx docgen build succeeds."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD = REPO / "scripts" / "docgen" / "build_all.py"


def verify_docgen_outputs(*, require_pdf: bool) -> int:
    """Assert staged docgen outputs match R-DOC-01 expectations.

    :param require_pdf: When ``True``, require a PDF under ``build/docgen/site/latex/``.
    :type require_pdf: bool

    :returns: Process exit code (``0`` on success).
    :rtype: int
    """
    html = REPO / "build" / "docgen" / "site" / "html" / "index.html"
    if not html.is_file():
        print(f"DOCGEN FAIL: expected HTML at {html}", file=sys.stderr)
        return 1

    index_pdf = REPO / "build" / "docgen" / "site" / "source" / "index_pdf.rst"
    if not index_pdf.is_file():
        print(f"DOCGEN FAIL: expected PDF master doc at {index_pdf}", file=sys.stderr)
        return 1
    pdf_index_text = index_pdf.read_text(encoding="utf-8")
    for required in ("guides/plugins", "guides/runtime_execution", "guides/glossary"):
        if required not in pdf_index_text:
            print(
                f"DOCGEN FAIL: index_pdf.rst must include {required} (PDF is the primary manual)",
                file=sys.stderr,
            )
            return 1
    if require_pdf:
        pdf_files = list((REPO / "build" / "docgen" / "site" / "latex").glob("*.pdf"))
        if not pdf_files:
            print("DOCGEN FAIL: expected PDF under build/docgen/site/latex/", file=sys.stderr)
            return 1
        print(f"DOCGEN PASS: {html} and {pdf_files[0]}")
    else:
        print(f"DOCGEN PASS: {html} (PDF not required)")

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for R-DOC-01 docgen regression.

    :param argv: Optional argument vector (defaults to ``sys.argv[1:]``).
    :type argv: list[str] | None, optional

    :returns: Process exit code (``0`` on success).
    :rtype: int
    """
    parser = argparse.ArgumentParser(description="Verify Colosseum docgen build output")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip build; assert outputs under build/docgen/ (for CI after phased build)",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip LaTeX/PDF build and PDF artifact check",
    )
    args = parser.parse_args(argv)

    require_pdf = not args.skip_pdf
    if not args.verify_only:
        if not BUILD.is_file():
            print(f"Missing docgen script: {BUILD}", file=sys.stderr)
            return 2

        if args.skip_pdf or shutil.which("latexmk") is None:
            if not args.skip_pdf:
                print("DOCGEN: latexmk not found; running HTML-only (--skip-pdf)")
            require_pdf = False
            cmd = [sys.executable, str(BUILD), "--skip-pdf"]
        else:
            cmd = [sys.executable, str(BUILD)]

        proc = subprocess.run(cmd, cwd=REPO, timeout=900)
        if proc.returncode != 0:
            print("DOCGEN FAIL: build_all.py returned non-zero", file=sys.stderr)
            return proc.returncode

    return verify_docgen_outputs(require_pdf=require_pdf)


if __name__ == "__main__":
    raise SystemExit(main())
