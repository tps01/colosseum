"""WATS WSJF JSON report generation."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config.metadata import merge_wats_metadata, metadata_sources_label, wats_export_enabled
from ..context import RuntimeContext
from ..database.records import MeasurementRecord, VerificationRecord
from ..results.aggregation import ResultAggregator

_WATS_START_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
)


def format_wats_start(dt: datetime) -> str:
    """Format an aware datetime for WATS ``start`` (Python 3.9+).

    WATS requires ``YYYY-MM-DDTHH:MM:SS±HH:MM`` with a colon in the offset.
    Do not use ``%:z`` (3.12+) or ``%z`` (no colon on 3.9).

    :param dt: Timezone-aware datetime.
    :type dt: datetime

    :returns: WATS-compatible timestamp string.
    :rtype: str

    :raises ValueError: When ``dt`` is naive or has no UTC offset.
    """
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("WATS start time requires a timezone-aware datetime")
    offset = dt.utcoffset()
    assert offset is not None
    wall = dt.strftime("%Y-%m-%dT%H:%M:%S")
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{wall}{sign}{hours:02d}:{minutes:02d}"


def _wats_status(status: str) -> str:
    if status == "PASS":
        return "P"
    if status == "ERROR":
        return "E"
    return "F"


def _overall_wats_result(
    verifications: list[VerificationRecord],
    aggregator: ResultAggregator,
) -> str:
    if aggregator.suite_error or aggregator.teardown_failed:
        return "E"
    if any(not row.optional and row.status == "ERROR" for row in verifications):
        return "E"
    if not aggregator.overall_pass():
        return "F"
    return "P"


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_string(value: object) -> bool:
    return isinstance(value, str)


def _build_units_lookup(
    measurements: list[MeasurementRecord],
) -> tuple[dict[tuple[str, str, str], str], dict[str, str]]:
    by_triple: dict[tuple[str, str, str], str] = {}
    by_key: dict[str, str] = {}
    for row in measurements:
        unit = row.units or ""
        by_triple[(row.domain, row.command, row.key)] = unit
        if unit:
            by_key[row.key] = unit
    return by_triple, by_key


def _units_for(
    row: VerificationRecord,
    by_triple: dict[tuple[str, str, str], str],
    by_key: dict[str, str],
) -> str:
    return by_triple.get((row.domain, row.command, row.key), by_key.get(row.key, ""))


def _parse_timestamp(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _step_timings(
    verifications: list[VerificationRecord],
    started: datetime,
) -> list[float]:
    timings: list[float] = []
    previous = started
    for row in verifications:
        ts = _parse_timestamp(row.timestamp)
        if ts is not None:
            if ts.tzinfo is None and previous.tzinfo is not None:
                ts = ts.replace(tzinfo=previous.tzinfo)
            delta = max((ts - previous).total_seconds(), 0.0)
            timings.append(delta)
            previous = ts
        else:
            timings.append(0.0)
    return timings


def _first_failure_step_id(verifications: list[VerificationRecord]) -> int | None:
    for index, row in enumerate(verifications, start=2):
        if not row.optional and row.status in ("FAIL", "ERROR"):
            return index
    return None


def _numeric_measurement(
    row: VerificationRecord,
    *,
    unit: str,
) -> dict[str, Any]:
    expected = row.expected
    actual = row.actual
    tolerance = row.tolerance if row.tolerance is not None else 0.0
    compare_op = row.compare_op or "GELE"
    status = _wats_status(row.status)

    if compare_op == "LOG":
        return {
            "compOp": "LOG",
            "status": status,
            "unit": unit,
            "value": float(actual),
            "lowLimit": None,
            "highLimit": None,
        }

    if compare_op == "GE":
        return {
            "compOp": "GE",
            "status": status,
            "unit": unit,
            "value": float(actual),
            "lowLimit": float(expected),
        }

    if compare_op == "LE":
        return {
            "compOp": "LE",
            "status": status,
            "unit": unit,
            "value": float(actual),
            "lowLimit": float(expected),
        }

    if compare_op == "EQ":
        return {
            "compOp": "EQ",
            "status": status,
            "unit": unit,
            "value": float(actual),
            "lowLimit": float(expected),
        }

    low = float(expected) - float(tolerance)
    high = float(expected) + float(tolerance)
    return {
        "compOp": "GELE",
        "status": status,
        "unit": unit,
        "value": float(actual),
        "lowLimit": low,
        "highLimit": high,
    }


def _step_name(row: VerificationRecord) -> str:
    if row.step_name:
        return row.step_name
    return row.key


def _verification_step(
    step_id: int,
    row: VerificationRecord,
    *,
    caused_failure: bool,
    unit: str,
    tot_time: float,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": step_id,
        "group": "M",
        "name": _step_name(row),
        "status": _wats_status(row.status),
        "tsGuid": row.key,
        "totTime": tot_time,
        "causedUUTFailure": caused_failure,
    }
    if row.message and row.status != "PASS":
        base["reportText"] = row.message

    expected = row.expected
    actual = row.actual

    if _is_number(actual) and _is_number(expected):
        base["stepType"] = "ET_NLT"
        base["numericMeas"] = [_numeric_measurement(row, unit=unit)]
        return base

    if row.compare_op == "LOG" and _is_number(actual):
        base["stepType"] = "ET_NLT"
        base["numericMeas"] = [_numeric_measurement(row, unit=unit)]
        return base

    if _is_string(actual) and _is_string(expected):
        base["stepType"] = "ET_SVT"
        base["stringMeas"] = [
            {
                "compOp": "EQ",
                "name": None,
                "status": _wats_status(row.status),
                "value": actual,
                "limit": expected,
            }
        ]
        return base

    if _is_string(actual) and expected is None:
        base["stepType"] = "ET_SVT"
        base["stringMeas"] = [
            {
                "compOp": "Log",
                "name": None,
                "status": _wats_status(row.status),
                "value": actual,
                "limit": None,
            }
        ]
        return base

    base["stepType"] = "ET_PFT"
    base["booleanMeas"] = [{"name": None, "status": _wats_status(row.status)}]
    return base


def _build_misc_infos(
    ctx: RuntimeContext, meta: dict[str, Any], test_name: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "description": "Colosseum Version:",
            "text": ctx.framework_version,
            "numeric": 0,
        },
        {
            "description": "Test Script File Version:",
            "text": test_name,
            "numeric": 0,
        },
    ]
    extra = meta.get("misc_infos")
    if isinstance(extra, list):
        for item in extra:
            if isinstance(item, dict) and "description" in item:
                rows.append(
                    {
                        "description": str(item.get("description", "")),
                        "text": item.get("text"),
                        "numeric": item.get("numeric"),
                    }
                )
    return rows


def _build_uut(meta: dict[str, Any]) -> dict[str, Any]:
    uut: dict[str, Any] = {"user": meta.get("user_name", "")}
    optional_fields = {
        "batchSN": "batch_serial",
        "fixtureId": "fixture_id",
        "comment": "comment",
    }
    for uut_key, meta_key in optional_fields.items():
        value = meta.get(meta_key, "")
        if value:
            uut[uut_key] = value
    return uut


def build_wats_report(
    ctx: RuntimeContext,
    aggregator: ResultAggregator,
    verifications: list[VerificationRecord],
    measurements: list[MeasurementRecord] | None = None,
    *,
    ended_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the WATS JSON payload for a completed test run."""
    meta = merge_wats_metadata(ctx)
    started = ctx.started_at
    if started is None:
        started = datetime.now(timezone.utc).astimezone()
    end = ended_at or datetime.now(timezone.utc).astimezone()
    tot_time = max((end - started).total_seconds(), 0.0)
    overall_result = _overall_wats_result(verifications, aggregator)
    overall_pass = overall_result == "P"

    measurement_rows = measurements or []
    by_triple, by_key = _build_units_lookup(measurement_rows)
    step_timings = _step_timings(verifications, started)
    failure_step_id = _first_failure_step_id(verifications)

    steps: list[dict[str, Any]] = []
    for offset, row in enumerate(verifications):
        step_id = offset + 2
        caused = failure_step_id == step_id
        steps.append(
            _verification_step(
                step_id,
                row,
                caused_failure=caused,
                unit=_units_for(row, by_triple, by_key),
                tot_time=step_timings[offset] if offset < len(step_timings) else 0.0,
            )
        )

    test_name = ctx.test_case_name
    seq_version = meta.get("seq_version", "").strip() or "0.0"
    root: dict[str, Any] = {
        "id": 1,
        "group": "M",
        "stepType": "SequenceCall",
        "name": "MainSequence Callback",
        "status": overall_result,
        "totTime": tot_time,
        "causedUUTFailure": not overall_pass,
        "steps": steps,
        "seqCall": {
            "path": test_name,
            "name": test_name,
            "version": seq_version,
        },
    }
    report_text = meta.get("report_text", "").strip()
    if report_text:
        root["reportText"] = report_text

    payload: dict[str, Any] = {
        "type": "T",
        "result": overall_result,
        "root": root,
        "pn": meta.get("uut", ""),
        "rev": meta.get("revision", ""),
        "sn": meta.get("serial_number", ""),
        "processCode": meta.get("process_code", ""),
        "location": meta.get("location", ""),
        "purpose": meta.get("test_intent", ""),
        "machineName": meta.get("machine_name", ""),
        "start": format_wats_start(started),
        "uut": _build_uut(meta),
        "miscInfos": _build_misc_infos(ctx, meta, test_name),
    }
    process_name = meta.get("process_name", "").strip()
    if process_name:
        payload["processName"] = process_name

    sub_units = meta.get("sub_units")
    if isinstance(sub_units, list) and sub_units:
        payload["subUnits"] = sub_units

    return payload


def wats_filename(ctx: RuntimeContext, ended_at: datetime) -> str:
    """Return the WATS report filename for a completed run."""
    stamp = ended_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"wats_{stamp}_{ctx.test_case_name}.json"


def _append_debug_log(output_dir: Path, level: str, message: str) -> None:
    """Append a line to ``debug.log`` when the run log file is already closed."""
    log_path = output_dir / "debug.log"
    if not log_path.is_file():
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {level} [colosseum] {message}\n")


def _log_wats(output_dir: Path, ctx: RuntimeContext, level: str, message: str) -> None:
    if ctx.logger is not None and ctx.logger.handlers:
        log_fn = getattr(ctx.logger, level.lower(), None)
        if callable(log_fn):
            log_fn(message)
            return
    _append_debug_log(output_dir, level.upper(), message)


def write_wats_report(
    output_dir: Path,
    ctx: RuntimeContext,
    aggregator: ResultAggregator,
    verifications: list[VerificationRecord],
    measurements: list[MeasurementRecord] | None = None,
) -> Path | None:
    """Write the WATS JSON report for a completed test run.

    :returns: Path to the written report file, or ``None`` when export is disabled.
    """
    if not wats_export_enabled(ctx):
        _log_wats(
            output_dir,
            ctx,
            "debug",
            f"WATS export skipped (no_artifacts={ctx.no_artifacts}, output_dir={ctx.output_dir})",
        )
        return None

    meta = merge_wats_metadata(ctx)
    sources = metadata_sources_label(ctx)
    _log_wats(output_dir, ctx, "debug", f"WATS metadata sources: {sources}")
    identity_keys = [
        key
        for key in ("uut", "serial_number", "revision", "process_code", "location")
        if str(meta.get(key, "")).strip()
    ]
    _log_wats(
        output_dir,
        ctx,
        "debug",
        f"WATS identity fields set: {identity_keys or '(none; best-effort defaults)'}",
    )

    ended_at = datetime.now(timezone.utc).astimezone()
    payload = build_wats_report(
        ctx,
        aggregator,
        verifications,
        measurements,
        ended_at=ended_at,
    )
    start = payload.get("start", "")
    if not isinstance(start, str) or not _WATS_START_RE.match(start):
        raise ValueError(f"WATS start timestamp is malformed: {start!r}")

    filename = wats_filename(ctx, ended_at)
    primary = output_dir / filename
    text = json.dumps(payload, indent=4) + "\n"
    primary.write_text(text, encoding="utf-8")

    folder = meta.get("wats_folder", "").strip()
    if folder:
        dest_dir = Path(folder)
        dest_dir.mkdir(parents=True, exist_ok=True)
        copy_path = dest_dir / filename
        shutil.copy2(primary, copy_path)
        _log_wats(output_dir, ctx, "info", f"Wrote WATS report: {primary} (copied to {copy_path})")
    else:
        _log_wats(output_dir, ctx, "info", f"Wrote WATS report: {primary}")

    _log_wats(
        output_dir,
        ctx,
        "debug",
        f"WATS report result={payload.get('result')} steps={len(verifications)} start={start}",
    )

    return primary
