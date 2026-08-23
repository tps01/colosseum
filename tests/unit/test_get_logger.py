"""Tests for colosseum.logging.get_logger."""

from __future__ import annotations

from colosseum.context import RuntimeContext
from colosseum.logging import get_logger
from colosseum.logging.setup import setup_logging


def test_get_logger_returns_child_logger() -> None:
    logger = get_logger("colosseum.test.child")
    assert logger.name == "colosseum.test.child"


def test_plugin_namespace_logger_writes_to_debug_log(unit_runtime_context: RuntimeContext) -> None:
    setup_logging(unit_runtime_context, console=False, file=True)
    plugin_log = get_logger("colosseum.template")
    plugin_log.debug("template debug line")
    assert unit_runtime_context.output_dir is not None
    text = (unit_runtime_context.output_dir / "debug.log").read_text(encoding="utf-8")
    assert "[colosseum.template] template debug line" in text
