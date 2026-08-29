"""CLI fixture: main() only; runner must finalize without endex() in script body."""

from __future__ import annotations

from tests.support.core_api import measure_value, verify_value


def main() -> None:
    measure_value(key="required", value=3.3)
    verify_value(key="required", expected_val=3.3, tolerance=0.1)
