from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .database import DatabaseManager
from .results.aggregation import ResultAggregator

if TYPE_CHECKING:
    from .config.loader import ConfigStore
    from .plugins.registry import PluginRegistry
else:
    SuiteSlotResult = object  # noqa: A001 — runtime placeholder for forward ref

_ACTIVE_CONTEXT: RuntimeContext | None = None


@dataclass
class RuntimeContext:
    config: ConfigStore | None
    output_dir: Path | None
    db: DatabaseManager
    logger: logging.Logger | None
    plugin_registry: PluginRegistry
    result_aggregator: ResultAggregator
    test_case_name: str
    suite_name: str | None
    config_path: Path | str | None
    framework_version: str
    phase: str = "test"
    finalized: bool = False
    final_exit_code: int | None = None
    debug_logging: bool = False
    no_artifacts: bool = False
    auto_finalize: bool = False
    runtime_ready: bool = False
    resource_cache: dict[str, Any] = field(default_factory=dict)
    config_warnings: list[str] = field(default_factory=list)
    suite_output_dir: Path | None = None
    suite_test_results: list[Any] = field(default_factory=list)
    suite_slot_results: list[Any] = field(default_factory=list)
    slot_finalized: bool = False
    slot_affects_suite_result: bool = False
    suite_finalized: bool = False
    rip_cord_triggered: bool = False
    slot_script_path: Path | None = None
    slot_test_index: int | None = None
    slot_repeat_index: int | None = None


def get_context() -> RuntimeContext:
    if _ACTIVE_CONTEXT is None:
        raise RuntimeError(
            "Runtime is not initialized. Call col.config.load_config() or use `colosseum run`."
        )
    return _ACTIVE_CONTEXT


def set_context(ctx: RuntimeContext) -> RuntimeContext:
    global _ACTIVE_CONTEXT
    _ACTIVE_CONTEXT = ctx
    return ctx


def _env_no_artifacts() -> bool:
    return os.environ.get("COLOSSEUM_NO_ARTIFACTS") == "1"


def apply_no_artifacts(ctx: RuntimeContext, *, no_artifacts: bool) -> None:
    """Enable no-artifacts mode before runtime bootstrap."""
    if not no_artifacts:
        return
    if ctx.runtime_ready or ctx.output_dir is not None:
        raise RuntimeError(
            "no_artifacts must be set before the runtime is bootstrapped "
            "(before the first col.* call or colosseum run output allocation)."
        )
    ctx.no_artifacts = True


def init_context(
    *,
    test_case_name: str,
    suite_name: str | None = None,
    config_path: Path | str | None = None,
    no_artifacts: bool = False,
    auto_finalize: bool = False,
) -> RuntimeContext:
    from . import __version__
    from .plugins.registry import PluginRegistry

    ctx = RuntimeContext(
        config=None,
        output_dir=None,
        db=DatabaseManager(),
        logger=None,
        plugin_registry=PluginRegistry(),
        result_aggregator=ResultAggregator(),
        test_case_name=test_case_name,
        suite_name=suite_name,
        config_path=config_path,
        framework_version=__version__,
        no_artifacts=no_artifacts or _env_no_artifacts(),
        auto_finalize=auto_finalize,
    )
    if auto_finalize:
        from .results.exit_policy import register_auto_finalize_hooks

        register_auto_finalize_hooks()
    return set_context(ctx)
