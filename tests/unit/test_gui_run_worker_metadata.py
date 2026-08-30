"""GUI run worker argv includes metadata flag."""

from __future__ import annotations

from pathlib import Path

from colosseum.gui.run_worker import RunKind, RunRequest, RunWorker


def test_build_argv_includes_metadata_flag(tmp_path: Path) -> None:
    worker = RunWorker(cwd=tmp_path)
    script = tmp_path / "test_demo.py"
    script.write_text("pass\n", encoding="utf-8")
    argv = worker._build_argv(
        RunRequest(
            RunKind.TEST,
            script,
            config_path="config.toml",
            metadata_path="meta.yaml",
            debug=True,
        )
    )
    assert "--metadata" in argv
    meta_index = argv.index("--metadata")
    assert argv[meta_index + 1] == "meta.yaml"
