from typing import TYPE_CHECKING

from .aggregation import OutcomeCounts, OutcomeRecord, ResultAggregator

if TYPE_CHECKING:
    from .exit_policy import endex as endex
    from .exit_policy import finalize_suite as finalize_suite
    from .exit_policy import register_auto_finalize_hooks as register_auto_finalize_hooks

__all__ = [
    "OutcomeCounts",
    "OutcomeRecord",
    "ResultAggregator",
    "endex",
    "finalize_suite",
    "register_auto_finalize_hooks",
]


def __getattr__(name: str) -> object:
    if name == "endex":
        from .exit_policy import endex as endex_fn

        return endex_fn
    if name == "finalize_suite":
        from .exit_policy import finalize_suite as finalize_suite_fn

        return finalize_suite_fn
    if name == "register_auto_finalize_hooks":
        from .exit_policy import register_auto_finalize_hooks as register_hooks_fn

        return register_hooks_fn
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
