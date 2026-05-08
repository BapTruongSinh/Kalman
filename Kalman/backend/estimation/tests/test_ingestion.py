"""Tests for live-compatible ingestion helpers."""

from datetime import datetime, timezone

import pytest

from estimation.ingestion import (
    RawRecord,
    ValidationResult,
    preprocess_single,
    validate_live_record,
)


def _raw(sm: float | None = 50.0, row_index: int = 0) -> RawRecord:
    return RawRecord(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        soil_moisture=sm,
        temperature=25.0,
        humidity=70.0,
        light=100.0,
        drip=0.0,
        fan=0.0,
        mist=0.0,
        row_index=row_index,
    )


def test_raw_record_is_immutable() -> None:
    raw = _raw(50.0)
    with pytest.raises(AttributeError):
        raw.soil_moisture = 51.0  # type: ignore[misc]


def test_validate_live_record_allows_optional_ancillary_fields() -> None:
    raw = RawRecord(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        soil_moisture=50.0,
        temperature=None,
        humidity=None,
        light=None,
        drip=None,
        fan=None,
        mist=None,
        row_index=0,
    )
    assert validate_live_record(raw).is_valid is True


def test_preprocess_single_skips_invalid_live_measurement() -> None:
    raw = _raw(None)
    processed = preprocess_single(
        raw,
        ValidationResult(is_valid=False, status="missing", reason="missing"),
    )
    assert processed.preprocess_status == "skipped"
    assert processed.soil_moisture is None
