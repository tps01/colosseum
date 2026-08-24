"""Required @command exception — run must exit 1 with an ERROR command row."""

from __future__ import annotations

from pathlib import Path

import colosseum as col
from colosseum.decorators import command

_REPO = Path(__file__).resolve().parents[3]
_CONFIG = _REPO / "tests" / "fixtures" / "core.toml"


@command
def _boom(*, key: str = "") -> None:
    raise RuntimeError("command procedural failure")


def main() -> None:
    col.config.load_config(str(_CONFIG))
    _boom(key="step")


if __name__ == "__main__":
    main()
    col.endex()
