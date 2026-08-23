"""Persist decorated verification results and feed the run result aggregator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, TypeVar, overload

from ..database import VerificationRow
from ..output import ensure_runtime_ready
from ._common import ensure_runtime_context, resolve_command, resolve_domain
from ._typing import ParamSpec
from .command import COLOSSEUM_DECORATOR

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class VerificationResult:
    """Outcome returned by ``@verification`` functions (``PASS``, ``FAIL``, or ``ERROR``).

    :ivar status: ``PASS``, ``FAIL``, or ``ERROR``.
    :vartype status: str
    :ivar message: Human-readable detail when status is not ``PASS``.
    :vartype message: str
    :ivar optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :vartype optional: bool
    :ivar actual: Measured value when the verifier computed one (optional).
    :vartype actual: object
    """

    status: str
    message: str = ""
    optional: bool = False
    actual: Any = None


def missing_measurement_result(*, key: str, optional: bool = False) -> VerificationResult:
    return VerificationResult(
        status="ERROR",
        message=f"no measurement for key={key}",
        optional=optional,
    )


@overload
def verification(func: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def verification(func: None = None, /) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def verification(_func: Callable[..., Any] | None = None) -> object:
    """Decorator that records verification rows and updates exit aggregation.

    Wrapped functions must accept ``key=`` and return :class:`VerificationResult` (or
    ``bool``). Look up prior measurements in the body with
    ``get_context().db.get_measurement(...)`` and return
    :func:`missing_measurement_result` when evidence is absent.

    :param _func: Function to wrap when used as ``@verification`` without parentheses.
    :type _func: Callable | None

    Wrapper kwargs (not part of the wrapped function signature unless declared there):

    :param key: Links this verification to prior measurement row(s).
    :type key: str
    :param optional: When ``True``, FAIL/ERROR does not fail the aggregate result.
    :type optional: bool
    :param expected_val: Stored in SQLite when provided (tolerance-style verifiers).
    :type expected_val: float
    :param minimum: Stored in SQLite when provided (minimum-style host verifiers).
    :type minimum: float

    :returns: The decorated callable.
    """

    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        domain = resolve_domain(func)
        command = resolve_command(func)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            ctx = ensure_runtime_context()
            ensure_runtime_ready(ctx)
            key = kwargs.get("key")
            optional = bool(kwargs.get("optional", False))
            if not key:
                result = VerificationResult(
                    status="ERROR", message=f"`{command}` requires `key=`", optional=optional
                )
                ctx.result_aggregator.record_verification(
                    result, key="", command=command, domain=domain
                )
                ctx.db.insert_verification(
                    VerificationRow(
                        domain=domain,
                        command=command,
                        key="<missing>",
                        expected=None,
                        actual=None,
                        status=result.status,
                        optional=result.optional,
                        message=result.message,
                    )
                )
                return result
            try:
                raw_result = func(*args, **kwargs)
                if isinstance(raw_result, VerificationResult):
                    result = raw_result
                elif isinstance(raw_result, bool):
                    result = VerificationResult(
                        status="PASS" if raw_result else "FAIL",
                        message="" if raw_result else "verification returned False",
                        optional=optional,
                    )
                else:
                    result = VerificationResult(
                        status="PASS", message=str(raw_result), optional=optional
                    )
            except Exception as exc:
                if ctx.logger is not None:
                    ctx.logger.exception(
                        "verification %s.%s key=%s status=ERROR",
                        domain,
                        command,
                        key,
                    )
                result = VerificationResult(status="ERROR", message=str(exc), optional=optional)
            ctx.result_aggregator.record_verification(
                result, key=str(key), command=command, domain=domain
            )
            expected = kwargs.get("expected_val", kwargs.get("minimum"))
            ctx.db.insert_verification(
                VerificationRow(
                    domain=domain,
                    command=command,
                    key=key,
                    expected=expected,
                    actual=result.actual,
                    status=result.status,
                    optional=result.optional,
                    message=result.message,
                )
            )
            if ctx.logger is not None:
                ctx.logger.debug(
                    "verification %s.%s key=%s expected=%r status=%s message=%r",
                    domain,
                    command,
                    key,
                    kwargs.get("expected_val"),
                    result.status,
                    result.message,
                )
                ctx.logger.info(
                    "verification %s.%s key=%s status=%s optional=%s",
                    domain,
                    command,
                    key,
                    result.status,
                    result.optional,
                )
            return result

        setattr(wrapper, COLOSSEUM_DECORATOR, "verification")
        return wrapper

    if _func is None:
        return decorate
    return decorate(_func)
