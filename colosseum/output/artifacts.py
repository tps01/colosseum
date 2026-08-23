from __future__ import annotations

from pathlib import Path

from ..context import get_context
from .paths import ensure_output_dir


def resolve_artifact_path(relative_path: str) -> Path:
    ctx = get_context()
    output_dir = ensure_output_dir(ctx, logical_name=ctx.test_case_name)
    candidate = (output_dir / relative_path).resolve()
    if not str(candidate).startswith(str(output_dir.resolve())):
        raise ValueError("Artifact path must remain inside the active output directory")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def register_artifact(kind: str, path: Path, description: str = "") -> int:
    ctx = get_context()
    ensure_output_dir(ctx, logical_name=ctx.test_case_name)
    return ctx.db.insert_artifact(kind=kind, path=str(path), description=description)
