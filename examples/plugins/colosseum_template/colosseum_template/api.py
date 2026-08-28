"""Public API for ``col.template`` — TODO: rename domain/namespace when forking."""

from __future__ import annotations

from colosseum.decorators import (
    VerificationResult,
    command,
    measurement,
    verification,
)
from colosseum.logging import get_logger

_logger = get_logger("colosseum.template")

_DEVICE_COUNTS: dict[int, int] = {}


def _device_count(device_id: int) -> int:
    return _DEVICE_COUNTS.setdefault(device_id, device_id * 10)


@command
def arm_device(*, device_id: int) -> None:
    """Load the configured device row and prepare it (example command)."""
    from colosseum.config.loader import ConfigError
    from colosseum.context import get_context

    ctx = get_context()
    if ctx.config is None:
        raise ConfigError("Configuration is not loaded. Call col.config.load_config(...) first.")
    # dotted path + id field from this plugin's ConfigSectionSpec
    row = ctx.config.require_item("template.device", device_id)
    serial = row["serial"]
    _logger.debug("arm_device device_id=%s serial=%s", device_id, serial)
    # TODO: Your code here — talk to hardware, set GPIO, etc.


@measurement
def measure_widget_count(*, device_id: int, key: str) -> float:
    """Return a simulated widget count for the configured device."""
    count = float(_device_count(device_id))
    _logger.debug("measure_widget_count device_id=%s key=%s count=%s", device_id, key, count)
    return count


@verification
def verify_widget_count(
    *,
    key: str,
    expected_val: float,
    tolerance: float = 0.0,
    optional: bool = False,
) -> VerificationResult:
    """Verify a prior measure_widget_count row."""
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement("template", "measure_widget_count", key, row_index=0)
    if row is None or row.value is None:
        _logger.debug("verify_widget_count key=%s missing measurement", key)
        return missing_measurement_result(key=key, optional=optional)
    actual = float(row.value)
    _logger.debug(
        "verify_widget_count key=%s expected=%s +/- %s actual=%s",
        key,
        expected_val,
        tolerance,
        actual,
    )
    if abs(actual - expected_val) <= tolerance:
        return VerificationResult(
            status="PASS", message="", optional=optional, actual=actual
        )
    return VerificationResult(
        status="FAIL",
        message=f"expected {expected_val} +/- {tolerance}, got {actual}",
        optional=optional,
        actual=actual,
    )
