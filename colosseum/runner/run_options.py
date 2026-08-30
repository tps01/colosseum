"""CLI run options shared by single-test and suite runners."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ExecutionMode = Literal["full", "procedure", "verify_only"]


@dataclass
class RunOptions:
    input_dir: Path | None = None
    outputs_root: Path | None = None
    execution_mode: ExecutionMode = "full"
    previous_output_dir: Path | None = None
    plugin_commands: list[str] = field(default_factory=list)
    show_faults: bool = False


def resolve_input_path(input_dir: Path | None, positional: str) -> Path:
    """Resolve a positional test/suite path against an optional input directory."""
    path = Path(positional)
    if input_dir is not None:
        path = input_dir / path
    return path.resolve()


def resolve_outputs_root(options: RunOptions) -> Path:
    """Return the directory where timestamped run folders are created."""
    if options.outputs_root is not None:
        return options.outputs_root
    return Path.cwd() / "outputs"
