"""Relax config/suite TOML: bare words on the RHS of ``key = value`` become strings."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

_KEY_VALUE = re.compile(r"^(?P<indent>\s*)(?P<key>[\w.-]+)\s*=\s*(?P<value>.+?)\s*$")


def _split_inline_comment(value_part: str) -> tuple[str, str]:
    in_single = False
    in_double = False
    for index, char in enumerate(value_part):
        if char == '"' and not in_single:
            in_double = not in_double
        elif char == "'" and not in_double:
            in_single = not in_single
        elif char == "#" and not in_single and not in_double:
            value = value_part[:index].rstrip()
            comment = value_part[index:].rstrip()
            return value, f" {comment}" if comment else ""
    return value_part.strip(), ""


def _is_numeric_literal(value: str) -> bool:
    try:
        if value.startswith(("0x", "0o", "0b")):
            int(value, 0)
            return True
        if any(ch in value for ch in (".", "e", "E")):
            float(value)
            return True
        int(value)
        return True
    except ValueError:
        return False


def _needs_quoting(value: str) -> bool:
    if not value:
        return False
    if value[0] in "\"'[{:":
        return False
    if value.lower() in ("true", "false"):
        return False
    return not _is_numeric_literal(value)


def prepare_toml_text(text: str) -> str:
    """Quote bare-word RHS values so ``model = keysight-e4407b`` is valid TOML."""
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            lines.append(line)
            continue

        match = _KEY_VALUE.match(line)
        if match is None:
            lines.append(line)
            continue

        raw_value, comment_suffix = _split_inline_comment(match.group("value"))
        if not _needs_quoting(raw_value):
            lines.append(line)
            continue

        escaped = raw_value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{match.group("indent")}{match.group("key")} = "{escaped}"{comment_suffix}')
    if text.endswith("\n"):
        return "\n".join(lines) + "\n"
    return "\n".join(lines)


def loads_relaxed(text: str) -> dict[str, Any]:
    return tomllib.loads(prepare_toml_text(text))


def read_relaxed_toml(path: Path) -> dict[str, Any]:
    """Read UTF-8 TOML from ``path`` with relaxed bare-word quoting (strips BOM)."""
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    text = data.decode("utf-8")
    return loads_relaxed(text)
