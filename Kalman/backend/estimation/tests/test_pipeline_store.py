"""
Tests for ``estimation.pipeline.store`` (Task #007).

Coverage targets
----------------
* ``map_result_to_cycle`` — pure field-mapping correctness (kf_ prefix, all
  columns, raw sensor passthrough from ProcessedRecord, None fallbacks).
* ``bulk_save_cycles`` — DB round-trip, count return, empty-sequence guard,
  uniqueness constraint enforcement.
* ``begin_run`` / ``end_run`` — status transitions, timestamp population,
  local object refresh, invalid-precondition errors.
* Traceability — persisted rows are queryable and carry the full FK chain
  (cycle → run → config); error/skipped rows store explicit status.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from django.db import IntegrityError

from estimation.ingestion.loader import RawRecord
from estimation.ingestion.preprocessor import ProcessedRecord
from estimation.ingestion.validator import ValidationResult
from estimation.kalman import CycleResult
from estimation.models import ExperimentRun, ExperimentConfig, PipelineCycle
from estimation.pipeline import (
    RunStateError,
    begin_run,
    bulk_save_cycles,
    end_run,
    map_result_to_cycle,
)

# ── Fixtures / helpers ────────────────────────────────────────────────────────

_TS = datetime(2024, 3, 15, 8, 0, 0, tzinfo=timezone.utc)


def _make_result(**overrides: object) -> CycleResult:
    """Factory for a valid ok-status ``CycleResult`` with sensible defaults."""
    defaults: dict[str, object] = dict(
        timestamp=_TS,
        cycle_index=0,
        raw_soil_moisture=55.0,
        preprocess_status="valid",
        arx_predicted=54.5,
        x_prior=54.5,
        P_prior=1.05,
        innovation=0.5,
        R=1.0,
        K=0.488,
        x_posterior=54.74,
        P_posterior=0.537,
        cycle_status="ok",
        adaptive_status="R_updated",
        latency_ms=3.1,
        error_message=None,
    )
    defaults.update(overrides)
    return CycleResult(**defaults)  # type: ignore[arg-type]


def _make_raw_record(**overrides: object) -> RawRecord:
    """Factory for a ``RawRecord`` with realistic sensor values."""
    defaults: dict[str, object] = dict(
        timestamp=_TS.replace(tzinfo=None),
        soil_moisture=55.0,
        temperature=27.3,
        humidity=62.0,
        light=3400.0,
        drip=0.0,
        mist=0.0,
        fan=1.0,
        row_index=0,
    )
    defaults.update(overrides)
    return RawRecord(**defaults)  # type: ignore[arg-type]


def _make_processed_record(**overrides: object) -> ProcessedRecord:
    """Factory for a ``ProcessedRecord`` wrapping a ``RawRecord``."""
    raw = _make_raw_record()
    validation = ValidationResult(is_valid=True, status="valid")
    defaults: dict[str, object] = dict(
        raw=raw,
        validation=validation,
        preprocess_status="valid",
        soil_moisture=raw.soil_moisture,
        temperature=raw.temperature,
        humidity=raw.humidity,
        light=raw.light,
        drip=raw.drip,
        mist=raw.mist,
        fan=raw.fan,
    )
    defaults.update(overrides)
    return ProcessedRecord(**defaults)  # type: ignore[arg-type]


@pytest.fixture()
def pending_run(db: object) -> ExperimentRun:
    """A saved ``ExperimentRun`` in PENDING status with a config."""
    run = ExperimentRun.objects.create(name="test_run_007")
    ExperimentConfig.objects.create(run=run)
    return run


@pytest.fixture()
def running_run(pending_run: ExperimentRun) -> ExperimentRun:
    """A ``PENDING`` run that has been started via ``begin_run``."""
    begin_run(pending_run)
    return pending_run


# ── TestMapResultToCycle ──────────────────────────────────────────────────────


class TestMapResultToCycle:
    """Pure mapping tests — no database writes."""

    def test_sample_ts_and_cycle_index(self, pending_run: ExperimentRun) -> None:
        result = _make_result(cycle_index=7)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.sample_ts == _TS
        assert cycle.cycle_index == 7

    def test_slice_and_source_type_applied(self, pending_run: ExperimentRun) -> None:
        result = _make_result()
        cycle = map_result_to_cycle(
            result, pending_run,
            slice_type="validation",
            source_type="mysql_replay",
        )
        assert cycle.slice_type == "validation"
        assert cycle.source_type == "mysql_replay"

    def test_default_source_type_is_csv_replay(self, pending_run: ExperimentRun) -> None:
        result = _make_result()
        cycle = map_result_to_cycle(result, pending_run, slice_type="test")
        assert cycle.source_type == "csv_replay"

    # ── kf_ prefix mapping ───────────────────────────────────────────────────

    def test_kf_x_prior(self, pending_run: ExperimentRun) -> None:
        result = _make_result(x_prior=54.123)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.kf_x_prior == pytest.approx(54.123)

    def test_kf_P_prior(self, pending_run: ExperimentRun) -> None:
        result = _make_result(P_prior=2.456)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.kf_P_prior == pytest.approx(2.456)

    def test_kf_innovation(self, pending_run: ExperimentRun) -> None:
        result = _make_result(innovation=0.789)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.kf_innovation == pytest.approx(0.789)

    def test_kf_R(self, pending_run: ExperimentRun) -> None:
        result = _make_result(R=3.0)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.kf_R == pytest.approx(3.0)

    def test_kf_K(self, pending_run: ExperimentRun) -> None:
        result = _make_result(K=0.488)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.kf_K == pytest.approx(0.488)

    def test_kf_x_posterior(self, pending_run: ExperimentRun) -> None:
        result = _make_result(x_posterior=54.999)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.kf_x_posterior == pytest.approx(54.999)

    def test_kf_P_posterior(self, pending_run: ExperimentRun) -> None:
        result = _make_result(P_posterior=0.512)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.kf_P_posterior == pytest.approx(0.512)

    # ── Scalar result fields ─────────────────────────────────────────────────

    def test_raw_soil_moisture(self, pending_run: ExperimentRun) -> None:
        result = _make_result(raw_soil_moisture=60.5)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.raw_soil_moisture == pytest.approx(60.5)

    def test_preprocess_status_valid(self, pending_run: ExperimentRun) -> None:
        result = _make_result(preprocess_status="valid")
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.preprocess_status == "valid"

    def test_preprocess_status_kept_last(self, pending_run: ExperimentRun) -> None:
        result = _make_result(preprocess_status="kept_last")
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.preprocess_status == "kept_last"

    def test_arx_predicted_value(self, pending_run: ExperimentRun) -> None:
        result = _make_result(arx_predicted=54.999)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.arx_predicted == pytest.approx(54.999)

    def test_arx_predicted_none(self, pending_run: ExperimentRun) -> None:
        result = _make_result(arx_predicted=None)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.arx_predicted is None

    # ── Cycle status and error ────────────────────────────────────────────────

    def test_ok_cycle_status(self, pending_run: ExperimentRun) -> None:
        result = _make_result(cycle_status="ok")
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.cycle_status == "ok"
        assert cycle.error_message is None

    def test_error_cycle_status_and_message(self, pending_run: ExperimentRun) -> None:
        result = _make_result(
            cycle_status="error",
            adaptive_status="skipped",
            error_message="unexpected boom",
            innovation=None,
            K=None,
        )
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.cycle_status == "error"
        assert cycle.error_message == "unexpected boom"

    def test_skipped_no_measurement_status(self, pending_run: ExperimentRun) -> None:
        result = _make_result(
            cycle_status="skipped_no_measurement",
            adaptive_status="R_skipped",
            innovation=None,
            K=None,
        )
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.cycle_status == "skipped_no_measurement"
        assert cycle.kf_innovation is None
        assert cycle.kf_K is None

    # ── ProcessedRecord raw sensor passthrough ────────────────────────────────

    def test_raw_sensor_fields_from_record(self, pending_run: ExperimentRun) -> None:
        record = _make_processed_record()
        result = _make_result()
        cycle = map_result_to_cycle(result, pending_run, slice_type="train", record=record)
        assert cycle.raw_temperature == pytest.approx(record.raw.temperature)
        assert cycle.raw_humidity == pytest.approx(record.raw.humidity)
        assert cycle.raw_light == pytest.approx(record.raw.light)
        assert cycle.raw_drip == pytest.approx(record.raw.drip)
        assert cycle.raw_mist == pytest.approx(record.raw.mist)
        assert cycle.raw_fan == pytest.approx(record.raw.fan)

    def test_no_record_leaves_sensor_fields_none(self, pending_run: ExperimentRun) -> None:
        result = _make_result()
        cycle = map_result_to_cycle(result, pending_run, slice_type="train", record=None)
        assert cycle.raw_temperature is None
        assert cycle.raw_humidity is None
        assert cycle.raw_light is None
        assert cycle.raw_drip is None
        assert cycle.raw_mist is None
        assert cycle.raw_fan is None

    def test_raw_soil_moisture_comes_from_result_not_record(
        self, pending_run: ExperimentRun
    ) -> None:
        """raw_soil_moisture is taken from CycleResult, not ProcessedRecord."""
        record = _make_processed_record()
        result = _make_result(raw_soil_moisture=99.0)
        cycle = map_result_to_cycle(result, pending_run, slice_type="train", record=record)
        assert cycle.raw_soil_moisture == pytest.approx(99.0)

    def test_returns_unsaved_instance(self, pending_run: ExperimentRun) -> None:
        """map_result_to_cycle must return an unsaved ORM object (pk is None)."""
        result = _make_result()
        cycle = map_result_to_cycle(result, pending_run, slice_type="train")
        assert cycle.pk is None

    def test_run_fk_set_correctly(self, pending_run: ExperimentRun) -> None:
        result = _make_result()
        cycle = map_result_to_cycle(result, pending_run, slice_type="test")
        assert cycle.run is pending_run


# ── TestBulkSaveCycles ────────────────────────────────────────────────────────


@pytest.mark.django_db()
class TestBulkSaveCycles:
    """Database persistence via bulk_save_cycles."""

    def _build_cycles(
        self,
        run: ExperimentRun,
        n: int,
        start_index: int = 0,
    ) -> list[PipelineCycle]:
        return [
            map_result_to_cycle(
                _make_result(cycle_index=start_index + i),
                run,
                slice_type="test",
            )
            for i in range(n)
        ]

    def test_returns_correct_count(self, pending_run: ExperimentRun) -> None:
        cycles = self._build_cycles(pending_run, 5)
        assert bulk_save_cycles(cycles) == 5

    def test_saved_rows_are_queryable(self, pending_run: ExperimentRun) -> None:
        bulk_save_cycles(self._build_cycles(pending_run, 3))
        assert PipelineCycle.objects.filter(run=pending_run).count() == 3

    def test_empty_sequence_returns_zero(self, pending_run: ExperimentRun) -> None:
        assert bulk_save_cycles([]) == 0
        assert PipelineCycle.objects.filter(run=pending_run).count() == 0

    def test_large_batch_all_saved(self, pending_run: ExperimentRun) -> None:
        """Exceeds the default batch_size=500 to verify multi-batch insertion."""
        count = bulk_save_cycles(self._build_cycles(pending_run, 501))
        assert count == 501
        assert PipelineCycle.objects.filter(run=pending_run).count() == 501

    def test_unique_constraint_on_run_cycle_index_raises(
        self, pending_run: ExperimentRun
    ) -> None:
        """Duplicate (run, cycle_index) must raise IntegrityError."""
        bulk_save_cycles(self._build_cycles(pending_run, 1))
        with pytest.raises(IntegrityError):
            bulk_save_cycles(self._build_cycles(pending_run, 1))

    def test_custom_batch_size_saves_all(self, pending_run: ExperimentRun) -> None:
        count = bulk_save_cycles(self._build_cycles(pending_run, 10), batch_size=3)
        assert count == 10
        assert PipelineCycle.objects.filter(run=pending_run).count() == 10


# ── TestRunStatusTransitions ─────────────────────────────────────────────────


@pytest.mark.django_db()
class TestRunStatusTransitions:
    """``begin_run`` and ``end_run`` lifecycle management."""

    def test_begin_run_sets_status_running(self, pending_run: ExperimentRun) -> None:
        begin_run(pending_run)
        assert pending_run.status == ExperimentRun.Status.RUNNING

    def test_begin_run_sets_started_at(self, pending_run: ExperimentRun) -> None:
        begin_run(pending_run)
        assert pending_run.started_at is not None

    def test_begin_run_refreshes_local_object(self, pending_run: ExperimentRun) -> None:
        """The local object must reflect DB state after begin_run."""
        begin_run(pending_run)
        from_db = ExperimentRun.objects.get(pk=pending_run.pk)
        assert from_db.status == ExperimentRun.Status.RUNNING
        assert pending_run.status == from_db.status

    def test_begin_run_non_pending_raises(self, running_run: ExperimentRun) -> None:
        with pytest.raises(RunStateError, match="current status"):
            begin_run(running_run)

    def test_end_run_completed(self, running_run: ExperimentRun) -> None:
        end_run(running_run, status="completed")
        assert running_run.status == ExperimentRun.Status.COMPLETED
        assert running_run.completed_at is not None

    def test_end_run_failed(self, running_run: ExperimentRun) -> None:
        end_run(running_run, status="failed")
        assert running_run.status == ExperimentRun.Status.FAILED

    def test_end_run_aborted(self, running_run: ExperimentRun) -> None:
        end_run(running_run, status="aborted")
        assert running_run.status == ExperimentRun.Status.ABORTED

    def test_end_run_refreshes_local_object(self, running_run: ExperimentRun) -> None:
        end_run(running_run, status="completed")
        from_db = ExperimentRun.objects.get(pk=running_run.pk)
        assert from_db.status == ExperimentRun.Status.COMPLETED
        assert running_run.status == from_db.status

    def test_end_run_non_running_raises(self, pending_run: ExperimentRun) -> None:
        with pytest.raises(RunStateError, match="current status"):
            end_run(pending_run, status="completed")

    def test_end_run_invalid_status_raises(self, running_run: ExperimentRun) -> None:
        with pytest.raises(ValueError, match="Invalid terminal status"):
            end_run(running_run, status="running")

    def test_end_run_unknown_status_raises(self, running_run: ExperimentRun) -> None:
        with pytest.raises(ValueError, match="Invalid terminal status"):
            end_run(running_run, status="bogus")


# ── TestTraceability ──────────────────────────────────────────────────────────


@pytest.mark.django_db()
class TestTraceability:
    """End-to-end traceability: cycle → run → config chain."""

    def test_cycle_fk_to_run(self, pending_run: ExperimentRun) -> None:
        cycle = map_result_to_cycle(_make_result(), pending_run, slice_type="test")
        bulk_save_cycles([cycle])
        saved = PipelineCycle.objects.get(run=pending_run, cycle_index=0)
        assert saved.run_id == pending_run.pk

    def test_cycle_traceable_to_config(self, pending_run: ExperimentRun) -> None:
        """Every cycle carries run FK → run.config is accessible."""
        cycle = map_result_to_cycle(_make_result(), pending_run, slice_type="test")
        bulk_save_cycles([cycle])
        saved = PipelineCycle.objects.select_related("run__config").get(
            run=pending_run, cycle_index=0
        )
        assert saved.run.config is not None
        assert saved.run.config.Q == pytest.approx(0.05)

    def test_slice_type_persisted(self, pending_run: ExperimentRun) -> None:
        for i, sl in enumerate(("train", "validation", "test")):
            cycle = map_result_to_cycle(_make_result(cycle_index=i), pending_run, slice_type=sl)
            bulk_save_cycles([cycle])
        counts = {
            sl: PipelineCycle.objects.filter(run=pending_run, slice_type=sl).count()
            for sl in ("train", "validation", "test")
        }
        assert all(v == 1 for v in counts.values())

    def test_error_cycle_has_explicit_status_and_message(
        self, pending_run: ExperimentRun
    ) -> None:
        """Error rows must carry cycle_status=error AND a non-empty error_message."""
        result = _make_result(
            cycle_status="error",
            adaptive_status="skipped",
            error_message="something exploded",
            innovation=None,
            K=None,
        )
        bulk_save_cycles([map_result_to_cycle(result, pending_run, slice_type="test")])
        saved = PipelineCycle.objects.get(run=pending_run, cycle_index=0)
        assert saved.cycle_status == "error"
        assert saved.error_message == "something exploded"

    def test_skipped_cycle_has_explicit_status(self, pending_run: ExperimentRun) -> None:
        """Skipped updates must store an explicit cycle_status (not default 'ok')."""
        result = _make_result(
            cycle_status="skipped_no_measurement",
            adaptive_status="R_skipped",
            raw_soil_moisture=None,
            innovation=None,
            K=None,
        )
        bulk_save_cycles([map_result_to_cycle(result, pending_run, slice_type="test")])
        saved = PipelineCycle.objects.get(run=pending_run, cycle_index=0)
        assert saved.cycle_status == "skipped_no_measurement"

    def test_full_db_round_trip_all_fields(self, pending_run: ExperimentRun) -> None:
        """After bulk_save, every mapped field is readable back from the database."""
        record = _make_processed_record()
        result = _make_result(
            cycle_index=42,
            raw_soil_moisture=58.1,
            arx_predicted=57.9,
            x_prior=57.9,
            P_prior=1.08,
            innovation=0.2,
            R=0.95,
            K=0.469,
            x_posterior=58.0,
            P_posterior=0.506,
        )
        cycle = map_result_to_cycle(result, pending_run, slice_type="validation", record=record)
        bulk_save_cycles([cycle])

        saved = PipelineCycle.objects.get(run=pending_run, cycle_index=42)
        assert saved.sample_ts == _TS
        assert saved.slice_type == "validation"
        assert saved.raw_soil_moisture == pytest.approx(58.1)
        assert saved.raw_temperature == pytest.approx(record.raw.temperature)
        assert saved.raw_humidity == pytest.approx(record.raw.humidity)
        assert saved.arx_predicted == pytest.approx(57.9)
        assert saved.kf_x_prior == pytest.approx(57.9)
        assert saved.kf_P_prior == pytest.approx(1.08)
        assert saved.kf_innovation == pytest.approx(0.2)
        assert saved.kf_R == pytest.approx(0.95)
        assert saved.kf_K == pytest.approx(0.469)
        assert saved.kf_x_posterior == pytest.approx(58.0)
        assert saved.kf_P_posterior == pytest.approx(0.506)
        assert saved.cycle_status == "ok"
        assert saved.error_message is None

    def test_mixed_status_batch(self, pending_run: ExperimentRun) -> None:
        """A realistic mix of ok/skipped/error cycles all persist correctly."""
        results = [
            _make_result(cycle_index=0, cycle_status="ok"),
            _make_result(
                cycle_index=1,
                cycle_status="skipped_no_measurement",
                adaptive_status="R_skipped",
                raw_soil_moisture=None,
                innovation=None,
                K=None,
            ),
            _make_result(
                cycle_index=2,
                cycle_status="error",
                adaptive_status="skipped",
                error_message="bad thing",
                innovation=None,
                K=None,
            ),
        ]
        cycles = [
            map_result_to_cycle(r, pending_run, slice_type="test") for r in results
        ]
        saved_count = bulk_save_cycles(cycles)
        assert saved_count == 3

        statuses = list(
            PipelineCycle.objects.filter(run=pending_run)
            .order_by("cycle_index")
            .values_list("cycle_status", flat=True)
        )
        assert statuses == ["ok", "skipped_no_measurement", "error"]
