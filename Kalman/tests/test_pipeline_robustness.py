"""Robustness tests for live one-step processing."""

from datetime import datetime, timedelta, timezone

from kalman.filter import AdaptiveKalmanCycle, KalmanConfig
from kalman.ingestion import RawRecord, preprocess_single, validate_live_record


def _raw(i: int, sm: float | None) -> RawRecord:
    return RawRecord(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i),
        soil_moisture=sm,
        temperature=25.0,
        humidity=70.0,
        light=100.0,
        drip=0.0,
        fan=0.0,
        mist=0.0,
        row_index=i,
    )


def test_live_step_sequence_handles_missing_and_out_of_range_values() -> None:
    est = AdaptiveKalmanCycle(KalmanConfig(x0=50.0))
    raw_records = [_raw(0, 50.0), _raw(1, None), _raw(2, 101.0), _raw(3, 51.0)]

    results = []
    for i, raw in enumerate(raw_records):
        validation = validate_live_record(raw)
        processed = preprocess_single(raw, validation)
        results.append(est.step(processed, cycle_index=i))

    assert len(results) == 4
    assert results[0].cycle_status == "ok"
    assert results[1].cycle_status == "skipped_no_measurement"
    assert results[2].cycle_status == "skipped_no_measurement"
    assert results[3].cycle_status == "ok"
