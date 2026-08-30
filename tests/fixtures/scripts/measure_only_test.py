"""Measure only — used for verify-only CLI regression."""

from __future__ import annotations

from pathlib import Path

import colosseum as col

from tests.support.core_api import measure_value

_REPO = Path(__file__).resolve().parents[3]
_CONFIG = _REPO / "tests" / "fixtures" / "core.toml"


def main() -> None:
    col.config.load_config(str(_CONFIG))
    measure_value(key="stored", value=4.2)


if __name__ == "__main__":
    main()
    col.endex()
