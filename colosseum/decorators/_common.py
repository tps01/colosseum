"""Shared helpers for measurement and verification decorators."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from ..context import RuntimeContext, get_context


def resolve_domain(func: Callable[..., Any]) -> str:
    """Resolve evidence domain from explicit attributes, then parent packages."""
    override = getattr(func, "__colosseum_domain__", None)
    if override:
        return str(override)
    module_name = func.__module__
    parts = module_name.split(".")
    for depth in range(len(parts), 0, -1):
        parent = sys.modules.get(".".join(parts[:depth]))
        if parent is None:
            continue
        domain = getattr(parent, "__colosseum_domain__", None)
        if domain:
            return str(domain)
    return "core"


def command_id_for_module(module: str, name: str) -> str:
    """Derive a command id from a public API module path convention."""
    parts = module.split(".")
    if len(parts) >= 4 and parts[-3] == "io" and parts[-2] == "api":
        group = parts[-1]
        return f"io.{group}.{name}"
    if len(parts) >= 3 and parts[-2] == "api":
        group = parts[-1]
        if not group.startswith("_"):
            return f"{group}.{name}"
    if len(parts) >= 3 and parts[-1] == "api":
        return f"{parts[-2]}.{name}"
    return name


def resolve_command(func: Callable[..., Any]) -> str:
    override = getattr(func, "__colosseum_command__", None)
    if override:
        return str(override)
    return command_id_for_module(func.__module__, func.__name__)


def ensure_runtime_context() -> RuntimeContext:
    return get_context()
