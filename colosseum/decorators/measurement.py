"""Persist decorated call results as SQLite measurement rows."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar, overload

from colosseum.database import MeasurementRow

from ._common import (
    ensure_runtime_context,
    resolve_command,
    resolve_domain,
    should_skip_measurement,
)
from ._kernel import log_evidence, log_evidence_error, record_error_event, short_repr
from ._typing import ParamSpec
from .command import COLOSSEUM_DECORATOR

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
R = TypeVar("R")


class MeasurementKeyError(RuntimeError):
    """Raised when a measurement is missing ``key=`` or duplicates an existing key."""


@overload
def measurement(func: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def measurement(
    func: None = None, /, *, multi_row: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def measurement(
    _func: Callable[..., Any] | None = None, *, multi_row: bool = False,
) -> object:
    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        domain = resolve_domain(func)
        command = resolve_command(func)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            ctx = ensure_runtime_context()
            if should_skip_measurement(ctx):
                return None
            key = kwargs.get("key")
            if not key:
                raise MeasurementKeyError(f"`{command}` requires `key=`")
            row_index = int(kwargs.get("row_index", 0))
            if multi_row and "row_index" not in kwargs:
                raise MeasurementKeyError(f"`{command}` with multi_row=True requires `row_index=`")
            if not multi_row:
                if ctx.db.list_measurements(domain=domain, command=command, key=key):
                    raise MeasurementKeyError(
                        f"Duplicate measurement key for ({domain}, {command}, {key})",
                    )
            elif (
                ctx.db.get_measurement(
                    domain=domain, command=command, key=key, row_index=row_index,
                )
                is not None
            ):
                raise MeasurementKeyError(
                    f"Duplicate measurement key for ({domain}, {command}, {key}, "
                    f"row_index={row_index})",
                )
            try:
                value = func(*args, **kwargs)
                ctx.db.insert_measurement(
                    MeasurementRow(
                        domain=domain,
                        command=command,
                        key=key,
                        row_index=row_index,
                        value=value,
                        status="PASS",
                    ),
                )
                log_evidence(
                    ctx,
                    kind="measurement",
                    domain=domain,
                    command=command,
                    key=key,
                    status="PASS",
                    detail=f"row_index={row_index} value={short_repr(value)}",
                )
                return value
            except Exception as exc:
                log_evidence_error(
                    ctx, kind="measurement", domain=domain, command=command, key=key,
                )
                record_error_event(ctx, domain=domain, command=command, exc=exc)
                ctx.db.insert_measurement(
                    MeasurementRow(
                        domain=domain,
                        command=command,
                        key=key,
                        row_index=row_index,
                        value=None,
                        status="ERROR",
                    ),
                )
                raise

        setattr(wrapper, COLOSSEUM_DECORATOR, "measurement")
        return wrapper

    if _func is None:
        return decorate
    return decorate(_func)
