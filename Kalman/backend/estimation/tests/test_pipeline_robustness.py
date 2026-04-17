"""
Task #011 — Missing, malformed, noisy, and repeated data (v1 pipeline robustness).

Exercises **load_csv → validate_batch → apply_preprocessing → AdaptiveKalmanCycle.replay**
per FR/NFR expectations: short gaps and noise must not crash the pipeline; invalid
rows carry explicit ``ValidationResult.status`` / ``reason`` and
``ProcessedRecord.preprocess_status``; Kalman ``CycleResult.error_message`` is set
when ``cycle_status == "error"``.

Run from ``Kalman/backend/``::

    pytest estimation/tests/test_pipeline_robustness.py -v

Real-dataset tests require ``../ARX/greenhouse_data.csv`` (``pytest.fail`` if absent).
"""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from estimation.ingestion import apply_preprocessing
from estimation.ingestion.loader import RawRecord, load_csv, split_chronological
from estimation.ingestion.validator import ValidationConfig, validate_batch
from estimation.kalman import AdaptiveKalmanCycle, KalmanConfig

_REPO_ROOT = Path(__file__).resolve().parents[4]
CSV_PATH = _REPO_ROOT / "ARX" / "greenhouse_data.csv"

_CSV_HEADERS = [
    "Timestamp",
    "Month",
    "Season",
    "Soil_Moisture",
    "Soil_Low_SP",
    "Soil_High_SP",
    "Temperature",
    "Humidity",
    "Light",
    "Drip",
    "Mist",
    "Fan",
]


def _csv_row(
    ts: str,
    sm: str,
    temp: str = "20.0",
    hum: str = "80.0",
    light: str = "50.0",
    drip: str = "0.0",
    mist: str = "0.0",
    fan: str = "0.0",
) -> dict[str, str]:
    return {
        "Timestamp": ts,
        "Month": "1",
        "Season": "winter",
        "Soil_Moisture": sm,
        "Soil_Low_SP": "51.0",
        "Soil_High_SP": "60.0",
        "Temperature": temp,
        "Humidity": hum,
        "Light": light,
        "Drip": drip,
        "Mist": mist,
        "Fan": fan,
    }


def _write_greenhouse_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_CSV_HEADERS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _replay_or_fail(est: AdaptiveKalmanCycle, processed: list[ProcessedRecord]) -> list:
    try:
        return est.replay(processed)
    except Exception as exc:  # pragma: no cover — guardrail for regression
        pytest.fail(f"Kalman replay raised unexpectedly: {exc}")


# ── Loader / malformed ────────────────────────────────────────────────────────


def test_malformed_numeric_empty_string_becomes_none_with_missing_reason(tmp_path):
    """Non-parseable Soil_Moisture cell → None; validator emits ``reason``."""
    p = tmp_path / "bad_sm.csv"
    base = datetime(2025, 1, 1, 0, 0, 0)
    rows = []
    for i in range(6):
        ts = (base + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S")
        sm = "" if i == 3 else f"{55.0 + i * 0.1:.6f}"
        rows.append(_csv_row(ts, sm))
    _write_greenhouse_csv(p, rows)

    loaded = load_csv(p)
    assert loaded[3].soil_moisture is None

    vals = validate_batch(loaded)
    assert vals[3].status == "missing"
    assert vals[3].reason
    assert "soil_moisture" in vals[3].reason.lower() or "none" in vals[3].reason.lower()


def test_unparseable_timestamp_row_skipped_without_crashing(tmp_path):
    """Loader skips bad timestamp rows and still returns a usable series."""
    p = tmp_path / "bad_ts.csv"
    base = datetime(2025, 2, 1, 12, 0, 0)
    rows = []
    for i in range(8):
        ts = (base + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
        if i == 4:
            ts = "not-a-valid-timestamp"
        rows.append(_csv_row(ts, f"{56.0 + i * 0.05:.4f}"))
    _write_greenhouse_csv(p, rows)

    loaded = load_csv(p)
    assert len(loaded) == 7
    assert all(isinstance(r.timestamp, datetime) for r in loaded)


# ── Validator diagnostics ─────────────────────────────────────────────────────


def test_validate_batch_reason_non_empty_for_out_of_range_and_repeat():
    """Failures must carry human-readable ``reason`` strings (NFR-007 style)."""
    base = datetime(2025, 3, 1, 0, 0, 0)
    recs: list[RawRecord] = []
    for i in range(6):
        ts = base + timedelta(minutes=i)
        sm = 58.0 if i < 5 else 58.0  # five identical then sixth same → repeat
        recs.append(
            RawRecord(ts, sm, 22.0, 70.0, 100.0, 0.0, 0.0, 0.0, row_index=i)
        )
    recs = list(recs)
    # spike out of range
    recs[2] = RawRecord(
        recs[2].timestamp,
        500.0,
        recs[2].temperature,
        recs[2].humidity,
        recs[2].light,
        recs[2].drip,
        recs[2].mist,
        recs[2].fan,
        row_index=2,
    )

    cfg = ValidationConfig(repeat_threshold=5)
    vals = validate_batch(recs, config=cfg)
    assert vals[2].status == "out_of_range"
    assert vals[2].reason
    assert "500" in vals[2].reason or "soil_moisture" in vals[2].reason

    # repeat fires once enough equal *valid* readings follow recovery
    recs2: list[RawRecord] = []
    for i in range(10):
        ts = base + timedelta(minutes=10 + i)
        sm = 60.0 if i < 5 else 61.0 + i * 0.01  # 0..4 same at 60
        recs2.append(RawRecord(ts, sm, 22.0, 70.0, 100.0, 0.0, 0.0, 0.0, row_index=i))
    vals2 = validate_batch(recs2, config=cfg)
    assert any(v.status == "suspicious_repeat" for v in vals2)
    rep = next(v for v in vals2 if v.status == "suspicious_repeat")
    assert "unchanged" in rep.reason.lower() or "consecutive" in rep.reason.lower()


# ── Full chain: keep_last / interpolate / skip ────────────────────────────────


def test_full_pipeline_keep_last_noise_gaps_and_spike_replay_completes(tmp_path):
    """Short burst of missing, noise, and out-of-range rows must not crash replay."""
    p = tmp_path / "noisy.csv"
    base = datetime(2025, 4, 1, 0, 0, 0)
    rng = np.random.default_rng(7)
    rows: list[dict[str, str]] = []
    for i in range(45):
        ts = (base + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S")
        if i in (5, 6, 7):
            sm = ""
        elif i == 15:
            sm = "999.0"
        elif 20 <= i <= 24:
            sm = f"{58.0 + 0.4 * rng.standard_normal():.6f}"
        else:
            sm = f"{55.0 + 0.2 * i + 0.05 * rng.standard_normal():.6f}"
        rows.append(_csv_row(ts, sm))
    _write_greenhouse_csv(p, rows)

    raw = load_csv(p)
    vals = validate_batch(raw)
    proc = apply_preprocessing(raw, vals, policy="keep_last")
    assert {p.preprocess_status for p in proc} <= {
        "valid",
        "kept_last",
        "skipped",
        "interpolated",
        "invalid",
    }
    for p_row, v in zip(proc, vals, strict=True):
        if not v.is_valid:
            assert v.reason

    cfg = KalmanConfig(x0=55.0)
    est = AdaptiveKalmanCycle(cfg)
    results = _replay_or_fail(est, proc)
    assert len(results) == len(proc)
    assert all(r.cycle_status in ("ok", "skipped_no_measurement", "error") for r in results)
    for r in results:
        if r.cycle_status == "error":
            assert r.error_message


def test_interpolate_policy_noisy_middle_replay_completes(tmp_path):
    p = tmp_path / "interp.csv"
    base = datetime(2025, 4, 2, 0, 0, 0)
    rows = []
    for i in range(30):
        ts = (base + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
        sm = "" if 10 <= i <= 12 else f"{56.0 + 0.1 * i:.4f}"
        rows.append(_csv_row(ts, sm))
    _write_greenhouse_csv(p, rows)

    raw = load_csv(p)
    vals = validate_batch(raw)
    proc = apply_preprocessing(raw, vals, policy="interpolate")
    assert any(p.preprocess_status == "interpolated" for p in proc)

    est = AdaptiveKalmanCycle(KalmanConfig(x0=56.0))
    results = _replay_or_fail(est, proc)
    assert len(results) == len(proc)


def test_skip_policy_long_missing_tail_replay_completes(tmp_path):
    p = tmp_path / "skip.csv"
    base = datetime(2025, 4, 3, 0, 0, 0)
    rows = []
    for i in range(25):
        ts = (base + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
        sm = "" if i >= 8 else f"{57.0 + 0.05 * i:.4f}"
        rows.append(_csv_row(ts, sm))
    _write_greenhouse_csv(p, rows)

    raw = load_csv(p)
    vals = validate_batch(raw)
    proc = apply_preprocessing(raw, vals, policy="skip")
    assert sum(1 for p in proc if p.preprocess_status == "skipped") >= 5

    est = AdaptiveKalmanCycle(KalmanConfig(x0=57.0))
    results = _replay_or_fail(est, proc)
    assert all(r.cycle_status == "skipped_no_measurement" for r in results[8:])


# ── Real greenhouse slice with injected defects ───────────────────────────────


def test_greenhouse_subset_injected_defects_replay_completes():
    """Derived fixture from real CSV: injected glitches must not abort replay."""
    if not CSV_PATH.exists():
        pytest.fail(
            f"Required dataset missing: {CSV_PATH}. "
            "Clone with ARX/greenhouse_data.csv for CI."
        )

    full = load_csv(CSV_PATH)
    assert len(full) > 600
    chunk = list(full[:600])
    # Inject: missing SM, out-of-range SM, ancillary outlier, duplicate-like flatline
    chunk[50] = replace(chunk[50], soil_moisture=None)
    chunk[120] = replace(chunk[120], soil_moisture=200.0)
    chunk[300] = replace(chunk[300], temperature=200.0)
    for i in range(400, 412):
        chunk[i] = replace(chunk[i], soil_moisture=55.0)

    vals = validate_batch(chunk, config=ValidationConfig(repeat_threshold=10))
    proc = apply_preprocessing(chunk, vals, policy="keep_last")

    est = AdaptiveKalmanCycle(KalmanConfig(x0=float(chunk[0].soil_moisture or 55.0)))
    results = _replay_or_fail(est, proc)
    assert len(results) == 600
    n_skip = sum(1 for r in results if r.cycle_status == "skipped_no_measurement")
    n_ok = sum(1 for r in results if r.cycle_status == "ok")
    assert n_ok + n_skip + sum(1 for r in results if r.cycle_status == "error") == 600
    assert n_ok > 100, "expected majority of steps to remain ok on real-ish data"


def test_split_then_train_slice_with_repeated_values_pipeline_stable(tmp_path):
    """Chronological split + train slice with repeated SM still replays."""
    p = tmp_path / "repeat_train.csv"
    base = datetime(2025, 5, 1, 0, 0, 0)
    rows = []
    for i in range(120):
        ts = (base + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
        sm = "58.0" if i < 15 else f"{58.0 + min(i, 40) * 0.02:.4f}"
        rows.append(_csv_row(ts, sm))
    _write_greenhouse_csv(p, rows)

    raw = load_csv(p)
    split = split_chronological(raw, train_ratio=0.6, val_ratio=0.2)
    train = split.train
    vals = validate_batch(train, config=ValidationConfig(repeat_threshold=12))
    proc = apply_preprocessing(train, vals, policy="keep_last")
    est = AdaptiveKalmanCycle(KalmanConfig(x0=58.0))
    results = _replay_or_fail(est, proc)
    assert len(results) == len(train)
