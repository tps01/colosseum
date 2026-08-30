"""Persist decorated command invocations and feed the run result aggregator."""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from inspect import signature
from typing import TYPE_CHECKING, Any, TypeVar, overload

from colosseum.database import CommandRow

from ._common import ensure_runtime_context, resolve_command, resolve_domain, should_skip_command
from ._kernel import log_evidence, log_evidence_error, record_error_event, short_repr
from ._typing import ParamSpec

if TYPE_CHECKING:
    from collections.abc import Callable

COLOSSEUM_DECORATOR = "__colosseum_decorator__"

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class CommandResult:
    status: str
    message: str = ""
    optional: bool = False


@overload
def command(func: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def command(func: None = None, /) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def command(_func: Callable[..., Any] | None = None) -> object:
    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        domain = resolve_domain(func)
        command_name = resolve_command(func)
        accepts_optional = "optional" in signature(func).parameters

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            ctx = ensure_runtime_context()
            if should_skip_command(ctx):
                return None
            key = str(kwargs.get("key", ""))
            optional = bool(kwargs.get("optional", False))
            call_kwargs = dict(kwargs)
            if not accepts_optional:
                call_kwargs.pop("optional", None)
            try:
                value = func(*args, **call_kwargs)
                if isinstance(value, CommandResult):
                    result, stored = value, None
                else:
                    result = CommandResult(status="PASS", message="", optional=optional)
                    stored = value
                ctx.db.insert_command(
                    CommandRow(
                        domain=domain,
                        command=command_name,
                        key=key,
                        result=stored,
                        status=result.status,
                        optional=result.optional,
                        message=result.message,
                    ),
                )
                ctx.result_aggregator.record_command(
                    result, key=key, command=command_name, domain=domain,
                )
                detail = f"value={short_repr(stored)}" if stored is not None else ""
                log_evidence(
                    ctx,
                    kind="command",
                    domain=domain,
                    command=command_name,
                    key=key,
                    status=result.status,
                    optional=result.optional,
                    detail=detail,
                )
                return value
            except Exception as exc:  # noqa: BLE001
                result = CommandResult(status="ERROR", message=str(exc), optional=optional)
                log_evidence_error(
                    ctx, kind="command", domain=domain, command=command_name, key=key,
                )
                record_error_event(ctx, domain=domain, command=command_name, exc=exc)
                ctx.db.insert_command(
                    CommandRow(
                        domain=domain,
                        command=command_name,
                        key=key,
                        result=None,
                        status="ERROR",
                        optional=optional,
                        message=str(exc),
                    ),
                )
                ctx.result_aggregator.record_command(
                    result, key=key, command=command_name, domain=domain,
                )
                if optional:
                    return None
                raise

        setattr(wrapper, COLOSSEUM_DECORATOR, "command")
        return wrapper

    if _func is None:
        return decorate
    return decorate(_func)
