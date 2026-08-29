"""Shared CI timing helpers for local profiling and GitHub Actions logs."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


def ci_timing_enabled() -> bool:
    """Return ``True`` when ``COLOSSEUM_CI_TIMING`` requests phase timing output.

    :returns: Whether phase timings should be printed.
    :rtype: bool
    """
    return os.environ.get("COLOSSEUM_CI_TIMING", "").strip().lower() in ("1", "true", "yes")


@contextmanager
def ci_phase(name: str) -> Iterator[None]:
    """Print ``TIMING <name>=Xs`` on exit when CI timing is enabled.

    :param name: Phase label (e.g. ``staging``, ``html``).
    :type name: str
    """
    if not ci_timing_enabled():
        yield
        return
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - start
        print(f"TIMING {name}={elapsed:.1f}s")
