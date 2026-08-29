"""WATS WSJF JSON report generation and metadata merge."""

from __future__ import annotations

import getpass
import json
import re
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from colosseum.context import RuntimeContext
    from colosseum.database.manager import MeasurementRecord, VerificationRecord
    from colosseum.results.aggregation import ResultAggregator

_WATS_START_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$",
)

STRING_METADATA_KEYS = frozenset(
    {
        "location",
        "process_code",
        "process_name",
        "revision",
        "serial_number",
        "test_intent",
        "user_name",
        "uut",
        "wats_folder",
        "report_text",
        "seq_version",
        "batch_serial",
        "fixture_id",
        "comment",
    },
)
COMPLEX_METADATA_KEYS = frozenset({"misc_infos", "sub_units"})
KNOWN_METADATA_KEYS = STRING_METADATA_KEYS | COMPLEX_METADATA_KEYS

_UUT_FIELD_MAP = (
    ("batchSN", "batch_serial"),
    ("fixtureId", "fixture_id"),
    ("comment", "comment"),
)


def format_wats_start(dt: datetime) -> str:
    """Format timezone-aware datetime as WATS ``start`` (offset with colon)."""
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


def _coerce_metadata_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_misc_infos(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {
            "description": str(item.get("description", "")),
            "text": item.get("text"),
            "numeric": item.get("numeric"),
        }
        for item in value
        if isinstance(item, dict)
    ]


def _normalize_sub_units(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [
        {
            "partType": str(item.get("partType", item.get("part_type", ""))),
            "pn": str(item.get("pn", "")),
            "rev": str(item.get("rev", "")),
            "sn": str(item.get("sn", "")),
        }
        for item in value
        if isinstance(item, dict)
    ]


def normalize_metadata_dict(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key in STRING_METADATA_KEYS:
            out[key] = _coerce_metadata_value(value)
        elif key == "misc_infos":
            normalized = _normalize_misc_infos(value)
            if normalized:
                out[key] = normalized
        elif key == "sub_units":
            normalized = _normalize_sub_units(value)
            if normalized:
                out[key] = normalized
    return out


def extract_colosseum_metadata_from_config(ctx: RuntimeContext) -> dict[str, Any]:
    if ctx.config is None:
        return {}
    section = ctx.config.get_section("colosseum.metadata")
    if not isinstance(section, dict):
        return {}
    return normalize_metadata_dict(section)


def metadata_sources_label(ctx: RuntimeContext) -> str:
    sources: list[str] = []
    if ctx.metadata_path:
        sources.append(f"yaml={ctx.metadata_path}")
    if extract_colosseum_metadata_from_config(ctx):
        sources.append("[colosseum.metadata]")
    return ", ".join(sources) if sources else "defaults (no metadata YAML or [colosseum.metadata])"


def default_wats_metadata() -> dict[str, str]:
    return {
        "location": "",
        "process_code": "",
        "process_name": "",
        "revision": "",
        "serial_number": "",
        "test_intent": "",
        "user_name": getpass.getuser(),
        "uut": "",
        "wats_folder": "",
        "report_text": "",
        "seq_version": "",
        "batch_serial": "",
        "fixture_id": "",
        "comment": "",
        "machine_name": socket.gethostname(),
    }


def merge_wats_metadata(ctx: RuntimeContext) -> dict[str, Any]:
    merged: dict[str, Any] = dict(default_wats_metadata())
    merged.update(extract_colosseum_metadata_from_config(ctx))
    merged.update(ctx.metadata_yaml)
    return merged


def wats_export_enabled(ctx: RuntimeContext) -> bool:
    return not ctx.no_artifacts and ctx.output_dir is not None


def _wats_status(status: str) -> str:
    return {"PASS": "P", "ERROR": "E"}.get(status, "F")


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


def _step_timings(verifications: list[VerificationRecord], started: datetime) -> list[float]:
    timings: list[float] = []
    previous = started
    for row in verifications:
        ts = _parse_timestamp(row.timestamp)
        if ts is None:
            timings.append(0.0)
            continue
        if ts.tzinfo is None and previous.tzinfo is not None:
            ts = ts.replace(tzinfo=previous.tzinfo)
        timings.append(max((ts - previous).total_seconds(), 0.0))
        previous = ts
    return timings


def _first_failure_step_id(verifications: list[VerificationRecord]) -> int | None:
    for index, row in enumerate(verifications, start=2):
        if not row.optional and row.status in ("FAIL", "ERROR"):
            return index
    return None


def _as_float(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("bool is not a numeric WATS limit")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f"expected numeric WATS limit, got {type(value)!r}")


def _numeric_extra(
    compare_op: str, expected: object, tolerance: float,
) -> dict[str, Any]:
    if compare_op == "LOG":
        return {"compOp": "LOG", "lowLimit": None, "highLimit": None}
    if compare_op == "GELE":
        exp = _as_float(expected)
        low = exp - tolerance
        high = exp + tolerance
        return {"compOp": "GELE", "lowLimit": low, "highLimit": high}
    return {"compOp": compare_op, "lowLimit": _as_float(expected)}


def _numeric_measurement(row: VerificationRecord, *, unit: str) -> dict[str, Any]:
    tolerance = float(row.tolerance if row.tolerance is not None else 0.0)
    compare_op = row.compare_op or "GELE"
    return {
        "status": _wats_status(row.status),
        "unit": unit,
        "value": float(row.actual),
        **_numeric_extra(compare_op, row.expected, tolerance),
    }


def _string_measurement(
    row: VerificationRecord, *, comp_op: str, limit: object | None,
) -> dict[str, Any]:
    return {
        "compOp": comp_op,
        "name": None,
        "status": _wats_status(row.status),
        "value": row.actual,
        "limit": limit,
    }


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
        "name": row.step_name or row.key,
        "status": _wats_status(row.status),
        "tsGuid": row.key,
        "totTime": tot_time,
        "causedUUTFailure": caused_failure,
    }
    if row.message and row.status != "PASS":
        base["reportText"] = row.message

    expected, actual = row.expected, row.actual
    is_num = isinstance(actual, (int, float)) and not isinstance(actual, bool)
    is_str = isinstance(actual, str)
    exp_num = isinstance(expected, (int, float)) and not isinstance(expected, bool)

    if (is_num and exp_num) or (row.compare_op == "LOG" and is_num):
        base["stepType"] = "ET_NLT"
        base["numericMeas"] = [_numeric_measurement(row, unit=unit)]
        return base
    if is_str and isinstance(expected, str):
        base["stepType"] = "ET_SVT"
        base["stringMeas"] = [_string_measurement(row, comp_op="EQ", limit=expected)]
        return base
    if is_str and expected is None:
        base["stepType"] = "ET_SVT"
        base["stringMeas"] = [_string_measurement(row, comp_op="Log", limit=None)]
        return base

    base["stepType"] = "ET_PFT"
    base["booleanMeas"] = [{"name": None, "status": _wats_status(row.status)}]
    return base


def _misc_infos(ctx: RuntimeContext, meta: dict[str, Any], test_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {"description": "Colosseum Version:", "text": ctx.framework_version, "numeric": 0},
        {"description": "Test Script File Version:", "text": test_name, "numeric": 0},
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
                    },
                )
    return rows


def _uut_payload(meta: dict[str, Any]) -> dict[str, Any]:
    uut: dict[str, Any] = {"user": meta.get("user_name", "")}
    for uut_key, meta_key in _UUT_FIELD_MAP:
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
    started = ctx.started_at or datetime.now(timezone.utc).astimezone()
    end = ended_at or datetime.now(timezone.utc).astimezone()
    tot_time = max((end - started).total_seconds(), 0.0)
    overall_result = _overall_wats_result(verifications, aggregator)

    by_triple, by_key = _build_units_lookup(measurements or [])
    step_timings = _step_timings(verifications, started)
    failure_step_id = _first_failure_step_id(verifications)

    steps = [
        _verification_step(
            offset + 2,
            row,
            caused_failure=failure_step_id == offset + 2,
            unit=_units_for(row, by_triple, by_key),
            tot_time=step_timings[offset] if offset < len(step_timings) else 0.0,
        )
        for offset, row in enumerate(verifications)
    ]

    test_name = ctx.test_case_name
    seq_version = meta.get("seq_version", "").strip() or "0.0"
    root: dict[str, Any] = {
        "id": 1,
        "group": "M",
        "stepType": "SequenceCall",
        "name": "MainSequence Callback",
        "status": overall_result,
        "totTime": tot_time,
        "causedUUTFailure": overall_result != "P",
        "steps": steps,
        "seqCall": {"path": test_name, "name": test_name, "version": seq_version},
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
        "uut": _uut_payload(meta),
        "miscInfos": _misc_infos(ctx, meta, test_name),
    }
    process_name = meta.get("process_name", "").strip()
    if process_name:
        payload["processName"] = process_name
    sub_units = meta.get("sub_units")
    if isinstance(sub_units, list) and sub_units:
        payload["subUnits"] = sub_units
    return payload


def wats_filename(ctx: RuntimeContext, ended_at: datetime) -> str:
    stamp = ended_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"wats_{stamp}_{ctx.test_case_name}.json"


def _log_wats(output_dir: Path, ctx: RuntimeContext, level: str, message: str) -> None:
    if ctx.logger is not None and ctx.logger.handlers:
        log_fn = getattr(ctx.logger, level.lower(), None)
        if callable(log_fn):
            log_fn(message)
            return
    log_path = output_dir / "debug.log"
    if log_path.is_file():
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {level.upper()} [colosseum] {message}\n")


def write_wats_report(
    output_dir: Path,
    ctx: RuntimeContext,
    aggregator: ResultAggregator,
    verifications: list[VerificationRecord],
    measurements: list[MeasurementRecord] | None = None,
) -> Path | None:
    """Write the WATS JSON report, or ``None`` when export is disabled."""
    if not wats_export_enabled(ctx):
        _log_wats(
            output_dir,
            ctx,
            "debug",
            f"WATS export skipped (no_artifacts={ctx.no_artifacts}, output_dir={ctx.output_dir})",
        )
        return None

    meta = merge_wats_metadata(ctx)
    _log_wats(output_dir, ctx, "debug", f"WATS metadata sources: {metadata_sources_label(ctx)}")
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
    payload = build_wats_report(ctx, aggregator, verifications, measurements, ended_at=ended_at)
    start = payload.get("start", "")
    if not isinstance(start, str) or not _WATS_START_RE.match(start):
        raise ValueError(f"WATS start timestamp is malformed: {start!r}")

    filename = wats_filename(ctx, ended_at)
    primary = output_dir / filename
    primary.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")

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
