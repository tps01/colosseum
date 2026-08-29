"""WATS smoke test with metadata for e2e fixtures."""

from __future__ import annotations

from pathlib import Path

import colosseum as col

from tests.support.core_api import measure_value, verify_value


def main() -> None:
    measure_value(key="wats_rail", value=1.0)
    verify_value(key="wats_rail", expected_val=1.0, tolerance=0.0)


if __name__ == "__main__":
    main()
    col.endex()
