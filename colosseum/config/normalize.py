from __future__ import annotations

from typing import Any

from .sections import ConfigSectionSpec


def _get_dotted(raw: dict[str, Any], dotted: str) -> object | None:
    cursor: object = raw
    for part in dotted.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def normalize_sections(
    raw: dict[str, Any], specs: list[ConfigSectionSpec]
) -> dict[str, dict[int, dict[str, Any]]]:
    """Index each registered section by its integer ID field.

    Each spec is one dotted path. A single TOML table or an array of tables
    both become ``{id: row}``. Missing sections are omitted.

    :param raw: Nested dict from parsed bench TOML.
    :type raw: dict[str, Any]
    :param specs: Registered section contracts.
    :type specs: list[ConfigSectionSpec]

    :returns: ``{dotted_path: {id: row}}`` for sections present in ``raw``.
    :rtype: dict[str, dict[int, dict[str, Any]]]

    :raises ValueError: When a present section is not a table, an ID is missing,
        not an ``int``, or duplicated.
    """
    normalized: dict[str, dict[int, dict[str, Any]]] = {}
    for spec in specs:
        value = _get_dotted(raw, spec.dotted_path)
        if value is None:
            continue
        if isinstance(value, dict):
            rows = [value]
        elif isinstance(value, list):
            rows = value
        else:
            raise ValueError(f"Section `{spec.dotted_path}` must be table or array of tables")

        by_id: dict[int, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"Section `{spec.dotted_path}` contains non-table entries")
            row_id = row.get(spec.id_field)
            if row_id is None:
                raise ValueError(f"Missing id field `{spec.id_field}` in `{spec.dotted_path}`")
            if not isinstance(row_id, int):
                raise ValueError(f"ID field `{spec.id_field}` in `{spec.dotted_path}` must be int")
            if row_id in by_id:
                raise ValueError(f"Duplicate id `{row_id}` in `{spec.dotted_path}`")
            by_id[row_id] = row
        normalized[spec.dotted_path] = by_id
    return normalized
