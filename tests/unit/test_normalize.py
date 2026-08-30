"""U-CFG: config section normalization."""

from __future__ import annotations

import pytest

from colosseum.config.loader import normalize_sections
from colosseum.config.sections import ConfigSectionSpec


def _get_dotted(raw: dict, dotted: str) -> object | None:
    cursor: object = raw
    for part in dotted.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


PSU_SPEC = ConfigSectionSpec(
    dotted_path="equipment.psu",
    id_field="psu_id",
    required_keys=("driver", "resource"),
    optional_keys=("model",),
)

DMM_SPEC = ConfigSectionSpec(
    dotted_path="equipment.dmm",
    id_field="dmm_id",
    required_keys=("driver", "resource"),
    optional_keys=("model",),
)


@pytest.mark.requirement("U-CFG-01")
def test_single_table_normalizes_to_id_map() -> None:
    raw = {
        "equipment": {
            "psu": {"psu_id": 1, "driver": "sim", "resource": "SIM::1"},
        }
    }
    out = normalize_sections(raw, [PSU_SPEC])
    assert out["equipment.psu"][1]["driver"] == "sim"


@pytest.mark.requirement("U-CFG-01")
def test_array_of_tables_normalizes() -> None:
    raw = {
        "equipment": {
            "psu": [
                {"psu_id": 1, "driver": "sim", "resource": "A"},
                {"psu_id": 2, "driver": "sim", "resource": "B"},
            ]
        }
    }
    out = normalize_sections(raw, [PSU_SPEC])
    assert set(out["equipment.psu"]) == {1, 2}


def test_non_mapping_intermediate_path_is_absent() -> None:
    raw = {"equipment": "not-a-table"}
    out = normalize_sections(raw, [PSU_SPEC])
    assert out == {}


def test_missing_section_does_not_skip_later_specs() -> None:
    raw = {
        "equipment": {
            "dmm": {"dmm_id": 1, "driver": "sim", "resource": "SIM::DMM"},
        }
    }
    out = normalize_sections(raw, [PSU_SPEC, DMM_SPEC])
    assert "equipment.psu" not in out
    assert out["equipment.dmm"][1]["resource"] == "SIM::DMM"


@pytest.mark.requirement("U-CFG-02")
def test_duplicate_id_raises() -> None:
    raw = {
        "equipment": {
            "psu": [
                {"psu_id": 1, "driver": "sim", "resource": "A"},
                {"psu_id": 1, "driver": "sim", "resource": "B"},
            ]
        }
    }
    with pytest.raises(ValueError, match="Duplicate id"):
        normalize_sections(raw, [PSU_SPEC])


@pytest.mark.requirement("U-CFG-02")
def test_missing_id_field_raises() -> None:
    raw = {"equipment": {"psu": {"driver": "sim", "resource": "A"}}}
    with pytest.raises(ValueError, match="Missing id field"):
        normalize_sections(raw, [PSU_SPEC])


def test_non_int_id_raises() -> None:
    raw = {"equipment": {"psu": {"psu_id": "one", "driver": "sim", "resource": "A"}}}
    with pytest.raises(ValueError, match="must be int"):
        normalize_sections(raw, [PSU_SPEC])


def test_get_dotted_return_type_is_object_or_none() -> None:
    assert _get_dotted.__annotations__["return"] == "object | None"


def test_invalid_section_type_raises() -> None:
    raw = {"equipment": {"psu": "not-a-table"}}
    with pytest.raises(ValueError, match="must be table or array of tables"):
        normalize_sections(raw, [PSU_SPEC])


def test_non_table_array_entry_raises() -> None:
    raw = {"equipment": {"psu": [{"psu_id": 1, "driver": "sim", "resource": "A"}, "bad"]}}
    with pytest.raises(ValueError, match="non-table entries"):
        normalize_sections(raw, [PSU_SPEC])
