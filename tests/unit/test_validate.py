"""U-CFG-03: unknown keys and validators."""

from __future__ import annotations

from colosseum.config.sections import ConfigSectionSpec
from colosseum.config.validate import collect_unknown_key_warnings, run_section_validators


SPEC = ConfigSectionSpec(
    dotted_path="equipment.psu",
    id_field="psu_id",
    required_keys=("driver",),
    optional_keys=("resource",),
)


def test_unknown_key_warning_not_silent() -> None:
    normalized = {
        "equipment.psu": {
            1: {"psu_id": 1, "driver": "sim", "typo_field": 99},
        }
    }
    warnings = collect_unknown_key_warnings(normalized, {SPEC.dotted_path: SPEC})
    assert any("typo_field" in w for w in warnings)


def test_validator_messages_collected() -> None:
    def reject_sim(row: dict) -> list[str]:
        if row.get("driver") == "sim":
            return ["sim not allowed in this test validator"]
        return []

    normalized = {"equipment.psu": {1: {"psu_id": 1, "driver": "sim"}}}
    msgs = run_section_validators(
        normalized,
        {SPEC.dotted_path: [reject_sim]},
    )
    assert msgs == ["sim not allowed in this test validator"]
