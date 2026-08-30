"""Record active output_dir name during main() for e2e finalize specification."""

from __future__ import annotations

from pathlib import Path

import colosseum as col


def main() -> None:
    ctx = col.context.get_context()
    assert ctx.output_dir is not None
    Path("active_dir_probe.txt").write_text(ctx.output_dir.name, encoding="utf-8")


if __name__ == "__main__":
    main()
    col.endex()
