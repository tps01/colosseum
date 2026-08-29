"""WATS start timestamp formatting (Python 3.9+)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from colosseum.summary.wats import format_wats_start


def test_format_wats_start_eastern_offset() -> None:
    eastern = timezone(timedelta(hours=-4))
    dt = datetime(2026, 8, 7, 8, 40, 48, tzinfo=eastern)
    assert format_wats_start(dt) == "2026-08-07T08:40:48-04:00"


def test_format_wats_start_positive_offset() -> None:
    cet = timezone(timedelta(hours=1))
    dt = datetime(2020, 1, 1, 9, 0, 0, tzinfo=cet)
    assert format_wats_start(dt) == "2020-01-01T09:00:00+01:00"


def test_format_wats_start_utc_uses_plus_zero_zero() -> None:
    dt = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert format_wats_start(dt) == "2020-01-01T12:00:00+00:00"
    assert "Z" not in format_wats_start(dt)


def test_format_wats_start_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        format_wats_start(datetime(2026, 8, 7, 8, 40, 48))


def test_format_wats_start_has_no_fractional_seconds() -> None:
    eastern = timezone(timedelta(hours=-4))
    dt = datetime(2026, 8, 7, 8, 40, 48, 123456, tzinfo=eastern)
    formatted = format_wats_start(dt)
    assert formatted == "2026-08-07T08:40:48-04:00"
    assert "." not in formatted


def test_format_wats_start_offset_has_colon_not_percent_z_style() -> None:
    eastern = timezone(timedelta(hours=-4))
    dt = datetime(2026, 8, 7, 8, 40, 48, tzinfo=eastern)
    formatted = format_wats_start(dt)
    assert formatted.endswith("-04:00")
    assert not formatted.endswith("-0400")
