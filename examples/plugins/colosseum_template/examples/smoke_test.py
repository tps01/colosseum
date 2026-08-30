"""Smoke test for the colosseum_template extension.

Run from the extension root after ``pip install -e .``::

    python examples/smoke_test.py

Or via Colosseum CLI::

    colosseum run examples/smoke_test.py --config configs/config.template.toml
"""

from __future__ import annotations

from pathlib import Path

import colosseum as col

_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "config.template.toml"


def main() -> None:
    # TODO: Point at your project config.toml.
    # For utility scripts with no outputs, use no_artifacts=True.
    col.config.load_config(str(_CONFIG))

    # TODO: Replace with your API calls (one col.* call per line, keyword args inline).
    col.template.arm_device(device_id=1)
    col.template.measure_widget_count(device_id=1, key="widgets")
    col.template.verify_widget_count(key="widgets", expected_val=10.0, tolerance=0.0)
    col.template.measure_power_rail(device_id=1, key="dut_3v3_rail")
    col.template.verify_power_rail(
        key="dut_3v3_rail",
        min_voltage_v=3.2,
        max_voltage_v=3.4,
        max_current_a=0.25,
        max_temperature_c=60.0,
    )


if __name__ == "__main__":
    main()
    col.endex()
