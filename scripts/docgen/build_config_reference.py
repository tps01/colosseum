#!/usr/bin/env python3
"""Generate bench TOML config reference RST from plugin ConfigSectionSpec."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _bootstrap import bootstrap

bootstrap()

from colosseum.plugins.loader import ensure_plugins_loaded  # noqa: E402
from colosseum.plugins.registry import PluginRegistry  # noqa: E402


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _format_keys(keys: tuple[str, ...]) -> str:
    if not keys:
        return "*(none)*"
    return ", ".join(f"``{key}``" for key in keys)


def build_config_reference_rst(*, output_path: Path) -> Path:
    """Generate bench TOML config reference RST from plugin ``ConfigSectionSpec``.

    :param output_path: Destination RST file path.
    :type output_path: Path

    :returns: ``output_path`` after writing.
    :rtype: Path
    """
    registry = PluginRegistry()
    ensure_plugins_loaded(registry)
    specs = sorted(registry.config_section_specs(), key=lambda spec: spec.dotted_path)

    lines = [
        "Bench configuration reference",
        "=============================",
        "",
        "Generated from plugin ``ConfigSectionSpec`` registration. Re-run "
        "``python scripts/docgen/build_all.py`` after changing required or optional keys.",
        "",
    ]
    if not specs:
        lines.extend(
            [
                "No plugin configuration sections are installed in this build.",
                "",
            ]
        )

    for spec in specs:
        title = spec.dotted_path.replace(".", " ").title()
        lines.extend(
            [
                title,
                "-" * len(title),
                "",
                f":ID field: ``{spec.id_field}``",
                "",
                ".. list-table::",
                "   :header-rows: 1",
                "   :widths: 28 72",
                "",
                "   * - Key class",
                "     - Keys",
                "   * - Required",
                f"     - {_format_keys(spec.required_keys)}",
                "   * - Optional",
                f"     - {_format_keys(spec.optional_keys)}",
                "",
            ]
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for bench configuration reference generation.

    :param argv: Optional argument vector (defaults to ``sys.argv[1:]``).
    :type argv: list[str] | None, optional

    :returns: Process exit code (``0`` on success).
    :rtype: int
    """
    parser = argparse.ArgumentParser(description="Generate bench config reference RST")
    parser.add_argument(
        "--output",
        type=Path,
        help="Default: build/docgen/site/source/guides/bench_config_reference.rst",
    )
    args = parser.parse_args(argv)
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    output = args.output or (
        repo_root / "build" / "docgen" / "site" / "source" / "guides" / "bench_config_reference.rst"
    )
    path = build_config_reference_rst(output_path=output)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
