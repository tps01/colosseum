"""Verify imported measurement — used with ``run -u`` regression."""

from __future__ import annotations

from pathlib import Path

import colosseum as col

from tests.support.core_api import verify_value

_REPO = Path(__file__).resolve().parents[3]
_CONFIG = _REPO / "tests" / "fixtures" / "core.toml"


def main() -> None:
    col.config.load_config(str(_CONFIG))
    verify_value(key="stored", expected_val=4.2, tolerance=0.1)


if __name__ == "__main__":
    main()
    col.endex()
