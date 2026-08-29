"""WATS test metadata from YAML files and ``[colosseum.metadata]`` bench TOML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from colosseum.context import get_context
from colosseum.summary.wats import (
    COMPLEX_METADATA_KEYS,
    KNOWN_METADATA_KEYS,
    extract_colosseum_metadata_from_config,
    merge_wats_metadata,
    metadata_sources_label,
    normalize_metadata_dict,
    wats_export_enabled,
)

__all__ = [
    "KNOWN_METADATA_KEYS",
    "COMPLEX_METADATA_KEYS",
    "extract_colosseum_metadata_from_config",
    "load_metadata",
    "load_metadata_yaml",
    "merge_wats_metadata",
    "metadata_sources_label",
    "validate_colosseum_metadata_table",
    "wats_export_enabled",
]


def validate_colosseum_metadata_table(raw: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in raw:
        if key not in KNOWN_METADATA_KEYS:
            warnings.append(
                f"Unknown key `{key}` in config section `colosseum.metadata`; ignored at runtime",
            )
        elif key in COMPLEX_METADATA_KEYS:
            warnings.append(
                f"Key `{key}` in config section `colosseum.metadata` is ignored; "
                "use metadata YAML for structured values",
            )
    return warnings


def load_metadata_yaml(path: str | Path) -> dict[str, Any]:
    from .loader import ConfigError

    metadata_path = Path(path).resolve()
    if not metadata_path.exists():
        raise ConfigError(f"Metadata file not found: {metadata_path}")
    try:
        data = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {metadata_path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"Metadata file must be a mapping: {metadata_path}")
    block = data.get("test_metadata", data)
    if not isinstance(block, dict):
        raise ConfigError(f"Metadata file `test_metadata` must be a mapping: {metadata_path}")
    return normalize_metadata_dict(block)


def load_metadata(path: str | Path) -> dict[str, Any]:
    ctx = get_context()
    parsed = load_metadata_yaml(path)
    ctx.metadata_yaml = parsed
    ctx.metadata_path = str(Path(path).resolve())
    if ctx.logger is not None:
        ctx.logger.info("Loaded WATS metadata from %s (%d keys)", ctx.metadata_path, len(parsed))
    if ctx.db.is_initialized():
        ctx.db.insert_run_metadata("metadata_path", ctx.metadata_path)
    return parsed
