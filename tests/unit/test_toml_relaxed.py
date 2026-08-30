"""Relaxed TOML parsing for config and suite files."""

from __future__ import annotations

import pytest

from colosseum.config.toml_relaxed import loads_relaxed, prepare_toml_text


def test_bare_words_become_strings() -> None:
    raw = loads_relaxed(
        """
[[equipment.speca]]
speca_id = 1
visa_backend = sim
model = keysight-e4407b
resource = GPIB::18::INSTR
"""
    )
    item = raw["equipment"]["speca"][0]
    assert item["visa_backend"] == "sim"
    assert item["model"] == "keysight-e4407b"
    assert item["resource"] == "GPIB::18::INSTR"


def test_booleans_and_numbers_unchanged() -> None:
    raw = loads_relaxed(
        """
[[equipment.psu]]
psu_id = 1
driver = sim
output = false
voltage = 3.3
timeout = 5
"""
    )
    item = raw["equipment"]["psu"][0]
    assert item["driver"] == "sim"
    assert item["output"] is False
    assert item["voltage"] == pytest.approx(3.3)
    assert item["timeout"] == 5


def test_quoted_values_preserved() -> None:
    raw = loads_relaxed('model = "already-quoted"\n')
    assert raw["model"] == "already-quoted"


def test_suite_name_without_quotes() -> None:
    raw = loads_relaxed('name = fixture_happy\n')
    assert raw["name"] == "fixture_happy"


def test_prepare_quotes_bare_word_only() -> None:
    prepared = prepare_toml_text("model = keysight-esg\noutput = false\n")
    assert 'model = "keysight-esg"' in prepared
    assert "output = false" in prepared
