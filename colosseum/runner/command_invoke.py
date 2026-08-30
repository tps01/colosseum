"""Parse and invoke plugin @command callables from CLI ``-c`` specifications."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any, cast

from colosseum.decorators.command import COLOSSEUM_DECORATOR
from colosseum.plugins.loader import ensure_plugins_loaded

if TYPE_CHECKING:
    from collections.abc import Callable

    from colosseum.context import RuntimeContext


class CommandInvokeError(RuntimeError):
    pass


def parse_plugin_command(spec: str) -> tuple[str, str, dict[str, Any]]:
    """Parse ``namespace.function,key=val,...`` into namespace, function, kwargs."""
    text = spec.strip()
    if not text:
        raise CommandInvokeError("command specification must not be empty")
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        raise CommandInvokeError("command specification must not be empty")
    target = parts[0]
    if "." not in target:
        raise CommandInvokeError(
            f"command target must be namespace.function, got {target!r}",
        )
    namespace, function = target.split(".", 1)
    if not namespace or not function:
        raise CommandInvokeError(f"invalid command target {target!r}")
    kwargs: dict[str, Any] = {}
    for item in parts[1:]:
        if "=" not in item:
            raise CommandInvokeError(f"expected key=value in command spec, got {item!r}")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise CommandInvokeError(f"empty keyword in command spec: {item!r}")
        kwargs[key] = _coerce_cli_value(raw_value.strip())
    return namespace, function, kwargs


def _coerce_cli_value(raw: str) -> Any:  # noqa: ANN401
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw


def resolve_plugin_command(namespace: str, function: str) -> Callable[..., Any]:
    from colosseum.context import get_context

    ctx = get_context()
    ensure_plugins_loaded(ctx.plugin_registry)
    try:
        module = ctx.plugin_registry.get_namespace(namespace)
    except KeyError as exc:
        raise CommandInvokeError(f"plugin namespace not found: {namespace}") from exc
    try:
        callable_obj = getattr(module, function)
    except AttributeError as exc:
        raise CommandInvokeError(
            f"plugin command not found: {namespace}.{function}",
        ) from exc
    if getattr(callable_obj, COLOSSEUM_DECORATOR, None) != "command":
        raise CommandInvokeError(f"{namespace}.{function} is not a @command")
    return cast("Callable[..., Any]", callable_obj)


def invoke_plugin_commands(_ctx: RuntimeContext, specs: list[str]) -> None:
    """Invoke one or more plugin commands in the active runtime context."""
    for spec in specs:
        namespace, function, kwargs = parse_plugin_command(spec)
        callable_obj = resolve_plugin_command(namespace, function)
        callable_obj(**kwargs)


def command_logical_name(spec: str) -> str:
    """Derive a run directory stem from the first ``-c`` specification."""
    namespace, function, _ = parse_plugin_command(spec)
    from colosseum.runner.runtime import sanitize_logical_name

    return sanitize_logical_name(f"{namespace}_{function}")
