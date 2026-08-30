"""Shared evidence decorator helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from colosseum.context import RuntimeContext


def short_repr(value: object, *, limit: int = 120) -> str:
    text = repr(value)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def log_evidence(
    ctx: RuntimeContext,
    *,
    kind: str,
    domain: str,
    command: str,
    key: str,
    status: str,
    optional: bool = False,
    detail: str = "",
) -> None:
    if ctx.logger is None:
        return
    if detail:
        ctx.logger.debug("%s %s.%s key=%s %s", kind, domain, command, key, detail)
    ctx.logger.info(
        "%s %s.%s key=%s status=%s optional=%s",
        kind,
        domain,
        command,
        key,
        status,
        optional,
    )


def log_evidence_error(
    ctx: RuntimeContext,
    *,
    kind: str,
    domain: str,
    command: str,
    key: str,
) -> None:
    if ctx.logger is not None:
        ctx.logger.exception("%s %s.%s key=%s status=ERROR", kind, domain, command, key)


def record_error_event(ctx: RuntimeContext, *, domain: str, command: str, exc: Exception) -> None:
    ctx.db.insert_event("ERROR", f"{domain}.{command}", str(exc))
