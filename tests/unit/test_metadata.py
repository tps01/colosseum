"""Metadata YAML and config TOML merge."""

from __future__ import annotations

from pathlib import Path

import pytest

from colosseum.config import ConfigError, load_config
from colosseum.config.metadata import (
    load_metadata_yaml,
    merge_wats_metadata,
    validate_colosseum_metadata_table,
    wats_export_enabled,
)


def test_validate_colosseum_metadata_unknown_key_warns() -> None:
    warnings = validate_colosseum_metadata_table({"location": "lab", "typo": "x"})
    assert any("typo" in warning for warning in warnings)


def test_load_metadata_yaml_parses_test_metadata_block(tmp_path: Path) -> None:
    path = tmp_path / "meta.yaml"
    path.write_text(
        "test_metadata:\n  uut: PART-1\n  serial_number: '42'\n",
        encoding="utf-8",
    )
    parsed = load_metadata_yaml(path)
    assert parsed["uut"] == "PART-1"
    assert parsed["serial_number"] == "42"


def test_merge_precedence_config_then_yaml(tmp_path: Path, io_bench) -> None:
    bench = io_bench(
        """
        [colosseum.metadata]
        location = "from-toml"
        uut = "TOML-PN"
        """
    )
    yaml_path = tmp_path / "meta.yaml"
    yaml_path.write_text(
        "test_metadata:\n  uut: YAML-PN\n  serial_number: '99'\n",
        encoding="utf-8",
    )
    load_config(bench, metadata_path=yaml_path)
    from colosseum.context import get_context

    merged = merge_wats_metadata(get_context())
    assert merged["location"] == "from-toml"
    assert merged["uut"] == "YAML-PN"
    assert merged["serial_number"] == "99"


def test_wats_export_enabled_with_artifacts(unit_runtime_context, tmp_path: Path) -> None:
    unit_runtime_context.output_dir = tmp_path
    assert wats_export_enabled(unit_runtime_context) is True


def test_wats_export_disabled_without_output_dir(unit_runtime_context) -> None:
    unit_runtime_context.output_dir = None
    assert wats_export_enabled(unit_runtime_context) is False


def test_playground_metadata_example_still_valid() -> None:
    playground = (
        Path(__file__).resolve().parents[3]
        / "playground"
        / "wats_examples"
        / "metadata_example1.yaml"
    )
    if not playground.exists():
        pytest.skip("playground metadata example not available")
    parsed = load_metadata_yaml(playground)
    assert parsed["uut"] == "PARTNUMBER"
    assert parsed["process_code"] == "1234"
    assert "process_name" not in parsed


def test_load_metadata_missing_file_raises(tmp_path: Path, unit_runtime_context) -> None:
    from colosseum.config.metadata import load_metadata

    with pytest.raises(ConfigError, match="not found"):
        load_metadata(tmp_path / "missing.yaml")
