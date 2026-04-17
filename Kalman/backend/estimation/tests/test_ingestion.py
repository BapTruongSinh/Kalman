"""
Tests for estimation.ingestion (task #003, revised after review).

Covers:
- CSV loading happy path against the real greenhouse_data.csv
- Timestamp parse failure and missing-column guards
- Validation: valid, missing, out-of-range, NaN, suspicious repeat
- Repeat detection: false-positive guard when None values are in the window
- Repeat detection semantic: invalid-for-other-reason rows still count toward
  stuck-sensor detection (history contains ALL records, not only valid ones)
- Preprocessing: keep_last, interpolate, skip — including out-of-range non-None values
- Interpolation formula: exact midpoint assertion (not loose range)
- Chronological split ratios, defensive sort, minimum-size guard
- End-to-end smoke test on real data
- Policy constants exported from public API

Run from Kalman/backend/:
    pytest estimation/tests/test_ingestion.py -v

The real dataset (`ARX/greenhouse_data.csv` at repo root) is a required fixture in this
repository.  Tests that depend on it call pytest.fail() — not pytest.skip() —
when the file is absent so that CI surfaces the problem immediately.
To run without it, remove/exclude the TestLoadCSV.test_loads_real_dataset and
TestEndToEndIngestion.test_full_pipeline_on_real_data tests explicitly.

Temporary file strategy
-----------------------
Tests that write CSV files use pytest's ``tmp_path`` fixture rather than
``tempfile.NamedTemporaryFile(delete=False)``.  This ensures temp files are
automatically cleaned up by pytest even when an assertion fails mid-test.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from estimation.ingestion import (
    INTERPOLATE,
    KEEP_LAST,
    SKIP,
    VALID_POLICIES,
    DatasetSplit,
    ProcessedRecord,
    RawRecord,
    ValidationConfig,
    ValidationResult,
    apply_preprocessing,
    load_csv,
    split_chronological,
    validate_batch,
    validate_record,
)

# ─── Path to the real dataset ──────────────────────────────────────────────────
# Two levels up from Kalman/backend/
_REPO_ROOT = Path(__file__).resolve().parents[4]
CSV_PATH = _REPO_ROOT / "ARX" / "greenhouse_data.csv"

_DATASET_REQUIRED_MSG = (
    f"Required dataset not found: {CSV_PATH}. "
    "Ensure ARX/greenhouse_data.csv is present at the repository root."
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_record(
    *,
    ts: str = "2025-01-01 00:00:00",
    sm: float | None = 55.0,
    temp: float | None = 22.0,
    hum: float | None = 70.0,
    light: float | None = 100.0,
    drip: float | None = 0.0,
    mist: float | None = 0.0,
    fan: float | None = 0.0,
    idx: int = 0,
) -> RawRecord:
    return RawRecord(
        timestamp=datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"),
        soil_moisture=sm,
        temperature=temp,
        humidity=hum,
        light=light,
        drip=drip,
        mist=mist,
        fan=fan,
        row_index=idx,
    )


def _write_csv(rows: list[dict], tmp_path: Path) -> Path:
    """Write *rows* into a temp CSV inside *tmp_path* and return the file path.

    Uses pytest's ``tmp_path`` fixture directory so the file is automatically
    removed after the test — even when an assertion raises mid-test.
    """
    fieldnames = [
        "Timestamp", "Month", "Season",
        "Soil_Moisture", "Soil_Low_SP", "Soil_High_SP",
        "Temperature", "Humidity", "Light", "Drip", "Mist", "Fan",
    ]
    out = tmp_path / "test_data.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            full = {k: "" for k in fieldnames}
            full.update(row)
            writer.writerow(full)
    return out


# ─── Loader tests ─────────────────────────────────────────────────────────────

class TestLoadCSV:

    def test_loads_real_dataset(self):
        """Real greenhouse CSV must load without errors."""
        if not CSV_PATH.exists():
            pytest.fail(_DATASET_REQUIRED_MSG)
        records = load_csv(CSV_PATH)
        assert len(records) == 105_120
        assert isinstance(records[0], RawRecord)

    def test_first_record_values(self):
        """First row of real dataset has expected Soil_Moisture."""
        if not CSV_PATH.exists():
            pytest.fail(_DATASET_REQUIRED_MSG)
        records = load_csv(CSV_PATH)
        assert records[0].soil_moisture == pytest.approx(58.0)
        assert records[0].timestamp == datetime(
            2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc
        )

    def test_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_csv(Path("/nonexistent/path/data.csv"))

    def test_raises_missing_column(self, tmp_path):
        # Write a CSV with only Timestamp and Temperature — Soil_Moisture absent
        tmp = tmp_path / "no_soil.csv"
        tmp.write_text("Timestamp,Temperature\n2025-01-01 00:00:00,20.0\n", encoding="utf-8")
        with pytest.raises(ValueError, match="missing required columns"):
            load_csv(tmp)

    def test_skips_bad_timestamp_rows(self, tmp_path):
        """Rows with unparseable timestamps are rejected at loader level.

        This is the first stage of malformed-data handling: malformed
        timestamps never reach the validator; only good rows are returned.
        """
        rows = [
            {"Timestamp": "NOT_A_DATE", "Soil_Moisture": "55.0",
             "Temperature": "22.0", "Humidity": "70.0", "Light": "100.0",
             "Drip": "0.0", "Mist": "0.0", "Fan": "0.0"},
            {"Timestamp": "2025-01-01 00:00:00", "Soil_Moisture": "55.0",
             "Temperature": "22.0", "Humidity": "70.0", "Light": "100.0",
             "Drip": "0.0", "Mist": "0.0", "Fan": "0.0"},
        ]
        tmp = _write_csv(rows, tmp_path)
        records = load_csv(tmp)
        assert len(records) == 1  # bad-timestamp row skipped

    def test_empty_numeric_field_becomes_none(self, tmp_path):
        """Non-parseable numeric cells are normalised to None (reported as 'missing')."""
        rows = [
            {"Timestamp": "2025-01-01 00:00:00", "Soil_Moisture": "",
             "Temperature": "22.0", "Humidity": "70.0", "Light": "100.0",
             "Drip": "0.0", "Mist": "0.0", "Fan": "0.0"},
        ]
        tmp = _write_csv(rows, tmp_path)
        records = load_csv(tmp)
        assert records[0].soil_moisture is None


# ─── Split tests ──────────────────────────────────────────────────────────────

class TestSplitChronological:

    def _dummy_records(self, n: int) -> list[RawRecord]:
        """Sequential timestamps so sort is stable and order tests are meaningful."""
        base = datetime(2025, 1, 1)
        return [
            _make_record(
                ts=(base + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S"),
                idx=i,
            )
            for i in range(n)
        ]

    def test_default_ratios_sum_to_n(self):
        records = self._dummy_records(100)
        split = split_chronological(records)
        assert split.total == 100
        assert len(split.train) == 60
        assert len(split.validation) == 20
        assert len(split.test) == 20

    def test_chronological_order_preserved(self):
        records = self._dummy_records(100)
        split = split_chronological(records)
        assert split.train[-1].timestamp < split.validation[0].timestamp
        assert split.validation[-1].timestamp < split.test[0].timestamp

    def test_raises_on_empty(self):
        with pytest.raises(ValueError):
            split_chronological([])

    def test_raises_on_bad_ratios(self):
        records = self._dummy_records(100)
        with pytest.raises(ValueError):
            split_chronological(records, train_ratio=0.6, val_ratio=0.5)

    def test_raises_on_too_small_dataset(self):
        """Dataset too small to produce non-empty train/val/test splits."""
        records = self._dummy_records(2)
        with pytest.raises(ValueError, match="too small"):
            split_chronological(records)

    def test_sort_corrects_out_of_order_input(self):
        """Defensive sort must reorder reversed-timestamp records correctly."""
        base = datetime(2025, 1, 1)
        # Create records with DESCENDING timestamps (worst-case out-of-order)
        records = [
            _make_record(
                ts=(base + timedelta(minutes=99 - i)).strftime("%Y-%m-%d %H:%M:%S"),
                idx=i,
            )
            for i in range(100)
        ]
        split = split_chronological(records)
        # After defensive sort, train must hold earlier timestamps than validation
        assert split.train[-1].timestamp < split.validation[0].timestamp
        assert split.validation[-1].timestamp < split.test[0].timestamp

    def test_real_dataset_split_sizes(self):
        if not CSV_PATH.exists():
            pytest.fail(_DATASET_REQUIRED_MSG)
        records = load_csv(CSV_PATH)
        split = split_chronological(records)
        assert split.total == len(records)
        assert abs(len(split.train) / split.total - 0.60) < 0.01
        assert abs(len(split.validation) / split.total - 0.20) < 0.01


# ─── Validator tests ──────────────────────────────────────────────────────────

class TestValidateRecord:

    def test_valid_record(self):
        record = _make_record()
        result = validate_record(record)
        assert result.is_valid
        assert result.status == "valid"

    def test_missing_field(self):
        record = _make_record(sm=None)
        result = validate_record(record)
        assert not result.is_valid
        assert result.status == "missing"
        assert "soil_moisture" in result.reason

    def test_soil_moisture_out_of_range_high(self):
        record = _make_record(sm=101.0)
        result = validate_record(record)
        assert not result.is_valid
        assert result.status == "out_of_range"

    def test_soil_moisture_out_of_range_low(self):
        record = _make_record(sm=-1.0)
        result = validate_record(record)
        assert not result.is_valid
        assert result.status == "out_of_range"

    def test_temperature_out_of_range(self):
        record = _make_record(temp=80.0)
        result = validate_record(record)
        assert not result.is_valid
        assert result.status == "out_of_range"

    def test_nan_field(self):
        record = _make_record(sm=float("nan"))
        result = validate_record(record)
        assert not result.is_valid
        assert result.status == "out_of_range"

    def test_suspicious_repeat_detected(self):
        cfg = ValidationConfig(repeat_threshold=3)
        prev = [_make_record(sm=55.0, idx=i) for i in range(2)]
        record = _make_record(sm=55.0, idx=2)
        result = validate_record(record, prev_records=prev, config=cfg)
        assert not result.is_valid
        assert result.status == "suspicious_repeat"

    def test_suspicious_repeat_not_triggered_below_threshold(self):
        cfg = ValidationConfig(repeat_threshold=5)
        prev = [_make_record(sm=55.0, idx=i) for i in range(2)]
        record = _make_record(sm=55.0, idx=2)
        result = validate_record(record, prev_records=prev, config=cfg)
        assert result.is_valid

    def test_repeat_no_false_positive_with_none_in_window(self):
        """[None, 55.0] window + current 55.0 must NOT trigger suspicious_repeat.

        With threshold=3 we need 3 consecutive valid identical values.
        A window containing None should not count as a valid comparable sample.
        """
        cfg = ValidationConfig(repeat_threshold=3)
        # Window has one None record + one 55.0 record → only 1 comparable value
        prev = [
            _make_record(sm=None, idx=0),   # missing — not comparable
            _make_record(sm=55.0, idx=1),
        ]
        record = _make_record(sm=55.0, idx=2)
        result = validate_record(record, prev_records=prev, config=cfg)
        # Only 1 comparable value in window (idx=1), need 2 → must NOT flag
        assert result.is_valid, (
            "False positive: repeat detected with only 1 comparable value in window"
        )

    def test_repeat_detected_when_row_invalid_for_other_reason(self):
        """A row invalid due to a *different* field still counts toward SM repeat.

        Semantic: ``validate_batch`` keeps ALL records in history (not only
        valid ones).  If row-1 has temperature=80 (out_of_range) but
        soil_moisture=55, that SM reading still contributes to stuck-sensor
        detection on subsequent rows.

        Sequence with threshold=3:
          idx=0  sm=55, temp=22  → valid
          idx=1  sm=55, temp=80  → out_of_range (other field), SM still 55
          idx=2  sm=55, temp=22  → should be suspicious_repeat (3 identical SMs)
        """
        cfg = ValidationConfig(repeat_threshold=3)
        records = [
            _make_record(sm=55.0, temp=22.0, idx=0),
            _make_record(sm=55.0, temp=80.0, idx=1),  # temp out_of_range
            _make_record(sm=55.0, temp=22.0, idx=2),
        ]
        results = validate_batch(records, config=cfg)
        assert results[0].status == "valid"
        assert results[1].status == "out_of_range"
        assert results[2].status == "suspicious_repeat", (
            "SM repeat not detected: row-1 invalid for different reason "
            "must still contribute to stuck-sensor window"
        )

    def test_validate_batch_with_real_data(self):
        if not CSV_PATH.exists():
            pytest.fail(_DATASET_REQUIRED_MSG)
        records = load_csv(CSV_PATH)[:1000]
        results = validate_batch(records)
        assert len(results) == len(records)
        valid_count = sum(1 for r in results if r.is_valid)
        assert valid_count > 990


# ─── Preprocessor tests ───────────────────────────────────────────────────────

class TestPreprocessKeepLast:

    def test_valid_records_pass_through(self):
        records = [_make_record(sm=55.0, idx=i) for i in range(3)]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="keep_last")
        assert all(p.preprocess_status == "valid" for p in processed)
        assert all(p.soil_moisture == 55.0 for p in processed)

    def test_missing_replaced_with_last_valid(self):
        records = [
            _make_record(sm=55.0, idx=0),
            _make_record(sm=None, idx=1),
            _make_record(sm=None, idx=2),
        ]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="keep_last")
        assert processed[0].preprocess_status == "valid"
        assert processed[1].preprocess_status == "kept_last"
        assert processed[1].soil_moisture == 55.0
        assert processed[2].soil_moisture == 55.0

    def test_no_prior_valid_keeps_none(self):
        records = [
            _make_record(sm=None, idx=0),
            _make_record(sm=55.0, idx=1),
        ]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="keep_last")
        assert processed[0].soil_moisture is None
        assert processed[1].soil_moisture == 55.0

    def test_out_of_range_replaced_not_passed_through(self):
        """out_of_range non-None value (101.0) must be replaced, not forwarded."""
        records = [
            _make_record(sm=55.0, idx=0),
            _make_record(sm=101.0, idx=1),  # out of range — must NOT pass to pipeline
            _make_record(sm=None, idx=2),
        ]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="keep_last")
        assert processed[1].preprocess_status == "kept_last"
        assert processed[1].soil_moisture == 55.0, (
            "Out-of-range value 101.0 was not replaced by last valid 55.0"
        )
        # Record 2 also uses last valid (55.0), since record 1 was invalid
        assert processed[2].soil_moisture == 55.0


class TestPreprocessSkip:

    def test_invalid_missing_marked_skipped_with_none(self):
        records = [
            _make_record(sm=55.0, idx=0),
            _make_record(sm=None, idx=1),
        ]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="skip")
        assert processed[0].preprocess_status == "valid"
        assert processed[1].preprocess_status == "skipped"
        assert processed[1].soil_moisture is None

    def test_out_of_range_set_to_none_when_skipped(self):
        """out_of_range non-None value must become None under skip policy."""
        records = [
            _make_record(sm=55.0, idx=0),
            _make_record(sm=101.0, idx=1),  # out of range
        ]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="skip")
        assert processed[1].preprocess_status == "skipped"
        assert processed[1].soil_moisture is None, (
            "Out-of-range value 101.0 was not set to None by skip policy"
        )

    def test_valid_records_pass_through(self):
        records = [_make_record(sm=55.0, idx=i) for i in range(5)]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="skip")
        assert all(p.preprocess_status == "valid" for p in processed)


class TestPreprocessInterpolate:

    def test_interpolated_between_two_valid(self):
        records = [
            _make_record(sm=50.0, idx=0),
            _make_record(sm=None, idx=1),  # missing
            _make_record(sm=60.0, idx=2),
        ]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="interpolate")
        assert processed[1].preprocess_status == "interpolated"
        # Midpoint between 50 and 60 at position 1 of gap [0..2] = 55.0
        assert processed[1].soil_moisture == pytest.approx(55.0)

    def test_out_of_range_interpolated_not_forwarded(self):
        """out_of_range non-None value must be discarded and interpolated."""
        records = [
            _make_record(sm=50.0, idx=0),
            _make_record(sm=101.0, idx=1),  # out of range — must be replaced
            _make_record(sm=60.0, idx=2),
        ]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="interpolate")
        assert processed[1].preprocess_status == "interpolated"
        assert processed[1].soil_moisture == pytest.approx(55.0), (
            "Out-of-range value 101.0 was not replaced by interpolated 55.0"
        )

    def test_no_next_valid_falls_back_to_last(self):
        records = [
            _make_record(sm=55.0, idx=0),
            _make_record(sm=None, idx=1),  # no next valid
        ]
        validations = [validate_record(r) for r in records]
        processed = apply_preprocessing(records, validations, policy="interpolate")
        assert processed[1].soil_moisture == 55.0


class TestPreprocessErrors:

    def test_mismatched_lengths_raise(self):
        records = [_make_record(idx=0)]
        validations: list[ValidationResult] = []
        with pytest.raises(ValueError, match="same length"):
            apply_preprocessing(records, validations, policy="keep_last")

    def test_unknown_policy_raises(self):
        records = [_make_record(idx=0)]
        validations = [validate_record(records[0])]
        with pytest.raises(ValueError, match="Unknown policy"):
            apply_preprocessing(records, validations, policy="bad_policy")


# ─── Public API contract ──────────────────────────────────────────────────────

class TestPublicAPIContracts:
    """Ensure exported constants match their expected string values.

    Downstream tasks (#004, #005) reference these constants to avoid
    hard-coding policy strings.  A typo or rename will break here first.
    """

    def test_policy_constants_exported(self):
        assert KEEP_LAST == "keep_last"
        assert INTERPOLATE == "interpolate"
        assert SKIP == "skip"

    def test_valid_policies_tuple_contains_all_three(self):
        assert set(VALID_POLICIES) == {"keep_last", "interpolate", "skip"}

    def test_policy_constants_accepted_by_apply_preprocessing(self):
        """Each exported constant must be a valid policy string at runtime."""
        records = [_make_record(sm=55.0, idx=i) for i in range(2)]
        validations = [validate_record(r) for r in records]
        for policy in VALID_POLICIES:
            result = apply_preprocessing(records, validations, policy=policy)
            assert len(result) == 2, f"apply_preprocessing failed for policy={policy!r}"


# ─── Integration smoke test ───────────────────────────────────────────────────

class TestEndToEndIngestion:

    def test_full_pipeline_on_real_data(self):
        """Load → split → validate → preprocess on the real CSV."""
        if not CSV_PATH.exists():
            pytest.fail(_DATASET_REQUIRED_MSG)

        records = load_csv(CSV_PATH)
        assert len(records) > 0

        split = split_chronological(records)
        assert split.total == len(records)

        validations = validate_batch(split.train)
        assert len(validations) == len(split.train)

        processed = apply_preprocessing(split.train, validations, policy="keep_last")
        assert len(processed) == len(split.train)
        assert isinstance(processed[0], ProcessedRecord)

        # Real data is clean; after keep_last no soil_moisture should be None
        none_sm = [p for p in processed if p.soil_moisture is None]
        assert len(none_sm) == 0, (
            f"{len(none_sm)} records still have None soil_moisture after keep_last"
        )
