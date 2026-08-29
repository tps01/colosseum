"""Persist decorated verification results and feed the run result aggregator."""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar, overload

from colosseum.database import VerificationRow

from ._common import ensure_runtime_context, resolve_command, resolve_domain
from ._kernel import log_evidence, log_evidence_error
from ._typing import ParamSpec
from .command import COLOSSEUM_DECORATOR

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class VerificationResult:
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


def _verification_fields(kwargs: dict[str, Any]) -> tuple[Any, str | None, float | None]:
    if kwargs.get("compare_op") == "LOG":
        return None, "LOG", None
    if "expected_val" in kwargs:
        return kwargs["expected_val"], "GELE", kwargs.get("tolerance", 0.0)
    if "minimum" in kwargs:
        return kwargs["minimum"], "GE", None
    if "maximum" in kwargs:
        return kwargs["maximum"], "LE", None
    if "exact" in kwargs:
        return kwargs["exact"], "EQ", None
    if "expected" in kwargs:
        expected = kwargs["expected"]
        return expected, "EQ" if isinstance(expected, str) else None, None
    return None, None, None


def _coerce_verification_result(raw_result: object, *, optional: bool) -> VerificationResult:
    if isinstance(raw_result, VerificationResult):
        return raw_result
    if isinstance(raw_result, bool):
        return VerificationResult(
            status="PASS" if raw_result else "FAIL",
            message="" if raw_result else "verification returned False",
            optional=optional,
        )
    return VerificationResult(status="PASS", message=str(raw_result), optional=optional)


@overload
def verification(func: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def verification(func: None = None, /) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def verification(_func: Callable[..., Any] | None = None) -> object:
    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        domain = resolve_domain(func)
        command = resolve_command(func)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            ctx = ensure_runtime_context()
            key = kwargs.get("key")
            optional = bool(kwargs.get("optional", False))
            step_name = kwargs.get("step_name")
            if step_name is not None:
                step_name = str(step_name).strip() or None
            if not key:
                result = VerificationResult(
                    status="ERROR", message=f"`{command}` requires `key=`", optional=optional,
                )
                ctx.result_aggregator.record_verification(
                    result, key="", command=command, domain=domain,
                )
                ctx.db.insert_verification(
                    VerificationRow(
                        domain=domain,
                        command=command,
                        key="<missing>",
                        status=result.status,
                        optional=result.optional,
                        message=result.message,
                        step_name=step_name,
                    ),
                )
                return result
            try:
                result = _coerce_verification_result(func(*args, **kwargs), optional=optional)
            except Exception as exc:  # noqa: BLE001
                log_evidence_error(
                    ctx, kind="verification", domain=domain, command=command, key=str(key),
                )
                result = VerificationResult(status="ERROR", message=str(exc), optional=optional)
            ctx.result_aggregator.record_verification(
                result, key=str(key), command=command, domain=domain,
            )
            expected, compare_op, tolerance = _verification_fields(kwargs)
            ctx.db.insert_verification(
                VerificationRow(
                    domain=domain,
                    command=command,
                    key=key,
                    expected=expected,
                    actual=result.actual,
                    tolerance=tolerance,
                    compare_op=compare_op,
                    status=result.status,
                    optional=result.optional,
                    message=result.message,
                    step_name=step_name,
                ),
            )
            log_evidence(
                ctx,
                kind="verification",
                domain=domain,
                command=command,
                key=str(key),
                status=result.status,
                optional=result.optional,
                detail=f"expected={kwargs.get('expected_val')!r} message={result.message!r}",
            )
            return result

        setattr(wrapper, COLOSSEUM_DECORATOR, "verification")
        return wrapper

    if _func is None:
        return decorate
    return decorate(_func)
