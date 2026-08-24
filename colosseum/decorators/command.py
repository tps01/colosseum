"""Persist decorated command invocations and feed the run result aggregator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from inspect import signature
from typing import Any, TypeVar, overload

from ..database import CommandRow
from ..output import ensure_runtime_ready
from ._common import ensure_runtime_context, resolve_command, resolve_domain
from ._typing import ParamSpec

COLOSSEUM_DECORATOR = "__colosseum_decorator__"

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class CommandResult:
    """Outcome returned by command bodies on logical failure without raising."""

    status: str
    message: str = ""
    optional: bool = False


@overload
def command(func: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def command(func: None = None, /) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def command(_func: Callable[..., Any] | None = None) -> object:
    """Decorator that records command rows, logs evidence, and fails the run on ERROR.

    :param _func: Function to wrap when used as ``@command`` without parentheses.
    :type _func: Callable | None

    Wrapper kwargs (optional, not required on the wrapped signature):

    :param key: Optional evidence key stored with the command row.
    :type key: str
    :param optional: When ``True``, ERROR/FAIL is recorded without failing the run or
        aborting remaining script steps.
    :type optional: bool

    :returns: The decorated callable. On a required-command exception, records ERROR then
        re-raises so remaining ``main()`` steps do not run; the runner still calls
        ``col.endex()`` to write the FAIL result. With ``optional=True``, records ERROR
        and returns ``None`` without re-raising.
    """

    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        domain = resolve_domain(func)
        command_name = resolve_command(func)
        accepts_optional = "optional" in signature(func).parameters

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            ctx = ensure_runtime_context()
            ensure_runtime_ready(ctx)
            key = str(kwargs.get("key", ""))
            optional = bool(kwargs.get("optional", False))
            call_kwargs = dict(kwargs)
            if not accepts_optional:
                call_kwargs.pop("optional", None)
            try:
                value = func(*args, **call_kwargs)
                if isinstance(value, CommandResult):
                    result = value
                    stored = None
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
                    )
                )
                ctx.result_aggregator.record_command(
                    result,
                    key=key,
                    command=command_name,
                    domain=domain,
                )
                if ctx.logger is not None:
                    if stored is not None:
                        value_repr = repr(stored)
                        if len(value_repr) > 120:
                            value_repr = value_repr[:117] + "..."
                        ctx.logger.debug(
                            "command %s.%s key=%s value=%s",
                            domain,
                            command_name,
                            key,
                            value_repr,
                        )
                    ctx.logger.info(
                        "command %s.%s key=%s status=%s optional=%s",
                        domain,
                        command_name,
                        key,
                        result.status,
                        result.optional,
                    )
                return value
            except Exception as exc:
                result = CommandResult(status="ERROR", message=str(exc), optional=optional)
                if ctx.logger is not None:
                    ctx.logger.exception(
                        "command %s.%s key=%s status=ERROR",
                        domain,
                        command_name,
                        key,
                    )
                ctx.db.insert_event("ERROR", f"{domain}.{command_name}", str(exc))
                ctx.db.insert_command(
                    CommandRow(
                        domain=domain,
                        command=command_name,
                        key=key,
                        result=None,
                        status="ERROR",
                        optional=optional,
                        message=str(exc),
                    )
                )
                ctx.result_aggregator.record_command(
                    result,
                    key=key,
                    command=command_name,
                    domain=domain,
                )
                if optional:
                    return None
                raise

        setattr(wrapper, COLOSSEUM_DECORATOR, "command")
        return wrapper

    if _func is None:
        return decorate
    return decorate(_func)
