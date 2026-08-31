"""Docgen PDF build command wiring."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]


def test_build_pdf_invokes_sphinx_and_latexmk(tmp_path) -> None:
    sys.path.insert(0, str(REPO / "scripts" / "docgen"))
    from build_pdf import build_pdf

    site_source = tmp_path / "source"
    latex_dir = tmp_path / "latex"
    site_source.mkdir()
    latex_dir.mkdir()
    (latex_dir / "colosseum.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
    pdf_path = latex_dir / "colosseum.pdf"

    with patch("build_pdf.require_latex_toolchain"), patch(
        "build_pdf.subprocess.run"
    ) as run_mock, patch("build_pdf._find_main_tex", return_value=latex_dir / "colosseum.tex"):
        def fake_run(cmd, **kwargs):
            if cmd and cmd[0] == "latexmk":
                pdf_path.write_bytes(b"%PDF")

        run_mock.side_effect = fake_run
        result = build_pdf(site_source=site_source, latex_dir=latex_dir, repo_root=REPO)

    assert result == pdf_path
    builders = [call.args[0] for call in run_mock.call_args_list]
    assert any("-b" in cmd and "latex" in cmd for cmd in builders)
    latexmk_calls = [call for call in run_mock.call_args_list if call.args[0][0] == "latexmk"]
    assert latexmk_calls
    latexmk_cmd = latexmk_calls[0].args[0]
    assert latexmk_calls[0].kwargs.get("cwd") == latex_dir
    assert "-cd" not in latexmk_cmd
    assert "colosseum.tex" in latexmk_cmd


def test_require_latex_toolchain_exits_when_missing() -> None:
    sys.path.insert(0, str(REPO / "scripts" / "docgen"))
    from build_pdf import require_latex_toolchain

    with patch("build_pdf.shutil.which", return_value=None):
        try:
            require_latex_toolchain()
            raised = False
        except SystemExit:
            raised = True
    assert raised
