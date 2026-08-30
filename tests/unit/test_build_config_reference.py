"""Docgen config reference generation."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[2]


def test_build_config_reference_handles_core_only_install(tmp_path) -> None:
    sys.path.insert(0, str(REPO))
    docgen_dir = REPO / "scripts" / "docgen"
    sys.path.insert(0, str(docgen_dir))
    from build_config_reference import build_config_reference_rst

    output = tmp_path / "config_reference.rst"
    empty_registry = MagicMock()
    empty_registry.config_section_specs.return_value = []
    with (
        patch("build_config_reference.PluginRegistry", return_value=empty_registry),
        patch("build_config_reference.ensure_plugins_loaded"),
    ):
        build_config_reference_rst(output_path=output)
    text = output.read_text(encoding="utf-8")
    assert "No plugin configuration sections are installed" in text
    assert "exactly one dotted TOML path" in text
    assert "exactly one integer ID field" in text
    assert "colosseum_equipment" not in text


def test_build_config_reference_emits_path_id_and_keys(tmp_path) -> None:
    sys.path.insert(0, str(REPO))
    docgen_dir = REPO / "scripts" / "docgen"
    sys.path.insert(0, str(docgen_dir))
    from build_config_reference import build_config_reference_rst
    from colosseum.config.sections import ConfigSectionSpec

    output = tmp_path / "config_reference.rst"
    registry = MagicMock()
    registry.config_section_specs.return_value = [
        ConfigSectionSpec(
            dotted_path="acme.device",
            id_field="device_id",
            required_keys=("serial",),
            optional_keys=("label",),
        )
    ]
    with (
        patch("build_config_reference.PluginRegistry", return_value=registry),
        patch("build_config_reference.ensure_plugins_loaded"),
    ):
        build_config_reference_rst(output_path=output)
    text = output.read_text(encoding="utf-8")
    assert ":Dotted path: ``acme.device``" in text
    assert ":ID field: ``device_id``" in text
    assert "``serial``" in text
    assert "``label``" in text
