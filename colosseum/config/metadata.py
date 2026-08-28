"""WATS test metadata from YAML files and ``[colosseum.metadata]`` bench TOML."""

from __future__ import annotations

import getpass
import socket
from pathlib import Path
from typing import Any

import yaml

from ..context import RuntimeContext, get_context

STRING_METADATA_KEYS = frozenset(
    {
        "location",
        "process_code",
        "process_name",
        "revision",
        "serial_number",
        "test_intent",
        "user_name",
        "uut",
        "wats_folder",
        "report_text",
        "seq_version",
        "batch_serial",
        "fixture_id",
        "comment",
    }
)

COMPLEX_METADATA_KEYS = frozenset({"misc_infos", "sub_units"})

KNOWN_METADATA_KEYS = STRING_METADATA_KEYS | COMPLEX_METADATA_KEYS


def _log_metadata(logger: object | None, level: str, msg: str, *args: object) -> None:
    if logger is None:
        return
    log_fn = getattr(logger, level, None)
    if callable(log_fn):
        log_fn(msg, *args)


def metadata_sources_label(ctx: RuntimeContext) -> str:
    """Describe which metadata inputs contributed to the merged WATS fields."""
    sources: list[str] = []
    if ctx.metadata_path:
        sources.append(f"yaml={ctx.metadata_path}")
    config_meta = extract_colosseum_metadata_from_config(ctx)
    if config_meta:
        sources.append("[colosseum.metadata]")
    if not sources:
        return "defaults (no metadata YAML or [colosseum.metadata])"
    return ", ".join(sources)


def _coerce_metadata_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_misc_infos(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "description": str(item.get("description", "")),
                "text": item.get("text"),
                "numeric": item.get("numeric"),
            }
        )
    return rows


def _normalize_sub_units(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "partType": str(item.get("partType", item.get("part_type", ""))),
                "pn": str(item.get("pn", "")),
                "rev": str(item.get("rev", "")),
                "sn": str(item.get("sn", "")),
            }
        )
    return rows


def _normalize_metadata_dict(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key in STRING_METADATA_KEYS:
            out[key] = _coerce_metadata_value(value)
        elif key == "misc_infos":
            normalized = _normalize_misc_infos(value)
            if normalized:
                out[key] = normalized
        elif key == "sub_units":
            normalized = _normalize_sub_units(value)
            if normalized:
                out[key] = normalized
    return out


def validate_colosseum_metadata_table(raw: dict[str, Any]) -> list[str]:
    """Return warning strings for unknown keys in ``[colosseum.metadata]``."""
    warnings: list[str] = []
    for key in raw:
        if key not in KNOWN_METADATA_KEYS:
            warnings.append(
                f"Unknown key `{key}` in config section `colosseum.metadata`; ignored at runtime"
            )
        elif key in COMPLEX_METADATA_KEYS:
            warnings.append(
                f"Key `{key}` in config section `colosseum.metadata` is ignored; "
                "use metadata YAML for structured values"
            )
    return warnings


def extract_colosseum_metadata_from_config(ctx: RuntimeContext) -> dict[str, Any]:
    """Read ``[colosseum.metadata]`` from the loaded bench TOML store."""
    if ctx.config is None:
        return {}
    section = ctx.config.get_section("colosseum.metadata")
    if not isinstance(section, dict):
        return {}
    return _normalize_metadata_dict(section)


def load_metadata_yaml(path: str | Path) -> dict[str, Any]:
    """Parse a metadata YAML file (``test_metadata:`` block).

    :param path: Path to the YAML file.
    :type path: str | Path

    :returns: Normalized metadata key/value strings.
    :rtype: dict[str, Any]

    :raises ConfigError: When the file is missing or invalid.
    """
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
    return _normalize_metadata_dict(block)


def load_metadata(path: str | Path) -> dict[str, Any]:
    """Load metadata YAML into the active run context.

    :param path: Path to the metadata YAML file.
    :type path: str | Path

    :returns: Parsed metadata dict.
    :rtype: dict[str, Any]

    :raises ConfigError: When the runtime or file is invalid.
    """
    from .loader import ConfigError

    ctx = get_context()
    parsed = load_metadata_yaml(path)
    ctx.metadata_yaml = parsed
    ctx.metadata_path = str(Path(path).resolve())
    _log_metadata(
        ctx.logger,
        "info",
        "Loaded WATS metadata from %s (%d keys)",
        ctx.metadata_path,
        len(parsed),
    )
    _log_metadata(
        ctx.logger,
        "debug",
        "WATS metadata keys from YAML: %s",
        sorted(parsed.keys()) or "(none)",
    )
    if ctx.db.is_initialized():
        ctx.db.insert_run_metadata("metadata_path", ctx.metadata_path)
    return parsed


def default_wats_metadata() -> dict[str, str]:
    """Runtime defaults for WATS identity fields."""
    return {
        "location": "",
        "process_code": "",
        "process_name": "",
        "revision": "",
        "serial_number": "",
        "test_intent": "",
        "user_name": getpass.getuser(),
        "uut": "",
        "wats_folder": "",
        "report_text": "",
        "seq_version": "",
        "batch_serial": "",
        "fixture_id": "",
        "comment": "",
        "machine_name": socket.gethostname(),
    }


def merge_wats_metadata(ctx: RuntimeContext) -> dict[str, Any]:
    """Merge defaults, bench TOML ``[colosseum.metadata]``, and loaded YAML.

    Precedence: defaults &lt; config table &lt; YAML file.
    """
    merged: dict[str, Any] = dict(default_wats_metadata())
    merged.update(extract_colosseum_metadata_from_config(ctx))
    merged.update(ctx.metadata_yaml)
    return merged


def wats_export_enabled(ctx: RuntimeContext) -> bool:
    """Return whether WATS JSON should be written for this run.

    Writes whenever artifacts are enabled, using runtime defaults when no metadata
    YAML or ``[colosseum.metadata]`` table is configured.
    """
    return not ctx.no_artifacts and ctx.output_dir is not None
