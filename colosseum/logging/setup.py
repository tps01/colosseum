from __future__ import annotations

import logging
import platform
import sys
from datetime import datetime, timezone

from ..context import RuntimeContext


def setup_logging(
    ctx: RuntimeContext,
    *,
    console: bool = False,
    console_level: int = logging.INFO,
    file: bool = True,
) -> logging.Logger:
    logger = logging.getLogger("colosseum")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    if file:
        assert ctx.output_dir is not None
        file_handler = logging.FileHandler(ctx.output_dir / "debug.log", mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if ctx.no_artifacts or ctx.output_dir is None:
        output_dir_line = "(none — no-artifacts mode)"
    else:
        output_dir_line = str(ctx.output_dir)
    header = [
        f"Colosseum version: {ctx.framework_version}",
        f"Python version: {sys.version}",
        f"Platform: {platform.platform()}",
        f"Test case: {ctx.test_case_name}",
        f"Suite: {ctx.suite_name or 'N/A'}",
        f"Start time: {datetime.now(timezone.utc).isoformat()}",
        f"Config file: {ctx.config_path or 'N/A'}",
        f"Output directory: {output_dir_line}",
    ]
    for line in header:
        logger.info(line)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a logger that participates in the Colosseum run log.

    ``setup_logging`` attaches handlers to the ``colosseum`` logger. Plugin and
    library code must use ``colosseum.<namespace>`` (for example
    ``colosseum.template``) or a child such as ``colosseum.template.api`` so
    records propagate into ``debug.log``. Names outside that tree never reach
    the run artifact.

    The file handler records DEBUG and above. Console output, when enabled,
    defaults to INFO.

    :param name: Logger name. Plugins use ``colosseum.<namespace>``.
    :type name: str

    :returns: Standard library logger for ``name``.
    :rtype: logging.Logger
    """
    return logging.getLogger(name)
