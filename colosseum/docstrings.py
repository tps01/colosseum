"""Shared Sphinx-style docstring helpers for first-party APIs."""

from __future__ import annotations

ParamSpec = tuple[str, str, str]  # name, type_name, description


def sphinx_param(name: str, type_name: str, description: str, *, optional: bool = False) -> str:
    type_line = f"{type_name}, optional" if optional else type_name
    return f":param {name}: {description}\n:type {name}: {type_line}"
