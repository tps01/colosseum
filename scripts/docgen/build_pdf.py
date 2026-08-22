"""Build PDF documentation from a staged Sphinx source tree."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_scripts_dir = Path(__file__).resolve().parents[1]
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from ci.timing import ci_phase  # noqa: E402

LATEX_INSTALL_HINT = """
LaTeX toolchain required for PDF output.

  Ubuntu/Debian: sudo apt-get install -y latexmk texlive-latex-recommended \\
      texlive-fonts-recommended texlive-latex-extra
  Windows: install MiKTeX or TeX Live and ensure latexmk is on PATH

Use --skip-pdf for HTML-only builds without LaTeX.
"""


def require_latex_toolchain() -> None:
    if shutil.which("latexmk") is None:
        raise SystemExit(LATEX_INSTALL_HINT.strip())


def _find_main_tex(latex_dir: Path) -> Path:
    candidates = sorted(latex_dir.glob("*.tex"))
    if not candidates:
        raise SystemExit(f"No .tex file found under {latex_dir}")
    preferred = latex_dir / "colosseum.tex"
    if preferred.is_file():
        return preferred
    if len(candidates) == 1:
        return candidates[0]
    raise SystemExit(f"Multiple .tex files in {latex_dir}; expected colosseum.tex")


def build_pdf(*, site_source: Path, latex_dir: Path, repo_root: Path) -> Path:
    """Run ``sphinx-build -b latex`` and ``latexmk``; return path to the PDF.

    :param site_source: Staged Sphinx source tree.
    :type site_source: Path
    :param latex_dir: LaTeX build output directory.
    :type latex_dir: Path
    :param repo_root: Repository root (sphinx working directory).
    :type repo_root: Path

    :returns: Path to the generated PDF file.
    :rtype: Path
    """
    require_latex_toolchain()
    latex_dir.mkdir(parents=True, exist_ok=True)
    with ci_phase("latex"):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "sphinx",
                "-b",
                "latex",
                str(site_source),
                str(latex_dir),
            ],
            cwd=repo_root,
            check=True,
        )
    tex_path = _find_main_tex(latex_dir)
    with ci_phase("latexmk"):
        subprocess.run(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-cd",
                str(tex_path),
            ],
            cwd=repo_root,
            check=True,
        )
    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.is_file():
        raise SystemExit(f"Expected PDF at {pdf_path}")
    return pdf_path
