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


def _require_float(payload: dict[str, object], field: str) -> float:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric, got {value!r}")
    return float(value)


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
    _logger.debug(
        "measure_widget_count device_id=%s key=%s count=%s",
        device_id,
        key,
        count,
    )
    return count


@measurement
def measure_power_rail(*, device_id: int, key: str) -> dict[str, object]:
    """Return a structured JSON measurement for values that belong together."""
    count = float(_device_count(device_id))
    payload: dict[str, object] = {
        "voltage_v": 3.287,
        "current_a": 0.142,
        "temperature_c": 41.8,
        "ripple_mv_pp": 18.6,
        "lock_status": "locked",
        "sample_count": int(count * 100),
    }
    _logger.debug(
        "measure_power_rail device_id=%s key=%s payload=%r",
        device_id,
        key,
        payload,
    )
    return payload


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
            status="PASS",
            message="",
            optional=optional,
            actual=actual,
        )
    return VerificationResult(
        status="FAIL",
        message=f"expected {expected_val} +/- {tolerance}, got {actual}",
        optional=optional,
        actual=actual,
    )


@verification
def verify_power_rail(
    *,
    key: str,
    min_voltage_v: float = 3.2,
    max_voltage_v: float = 3.4,
    max_current_a: float = 0.25,
    max_temperature_c: float = 60.0,
    required_lock_status: str = "locked",
    optional: bool = False,
) -> VerificationResult:
    """Verify several fields from the JSON payload saved by measure_power_rail."""
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement(
        "template",
        "measure_power_rail",
        key,
        row_index=0,
    )
    if row is None or row.value is None:
        _logger.debug("verify_power_rail key=%s missing measurement", key)
        return missing_measurement_result(key=key, optional=optional)
    if not isinstance(row.value, dict):
        return VerificationResult(
            status="ERROR",
            message=f"expected JSON object measurement, got {type(row.value).__name__}",
            optional=optional,
        )

    try:
        voltage = _require_float(row.value, "voltage_v")
        current = _require_float(row.value, "current_a")
        temperature = _require_float(row.value, "temperature_c")
        lock_status = str(row.value["lock_status"])
    except (KeyError, TypeError, ValueError) as exc:
        return VerificationResult(status="ERROR", message=str(exc), optional=optional)

    failures: list[str] = []
    if not min_voltage_v <= voltage <= max_voltage_v:
        failures.append(f"voltage_v={voltage} outside {min_voltage_v}..{max_voltage_v}")
    if current > max_current_a:
        failures.append(f"current_a={current} above {max_current_a}")
    if temperature > max_temperature_c:
        failures.append(f"temperature_c={temperature} above {max_temperature_c}")
    if lock_status != required_lock_status:
        failures.append(f"lock_status={lock_status!r}, expected {required_lock_status!r}")

    if failures:
        return VerificationResult(
            status="FAIL",
            message="; ".join(failures),
            optional=optional,
            actual=row.value,
        )
    return VerificationResult(
        status="PASS",
        message="",
        optional=optional,
        actual=row.value,
    )
