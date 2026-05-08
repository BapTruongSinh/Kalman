"""Tests for live-only PipelineCycle storage mapping."""

from datetime import datetime, timezone

import pytest

from estimation.kalman import CycleResult
from estimation.models import ExperimentRun, PipelineCycle
from estimation.pipeline.store import (
    begin_run,
    bulk_save_cycles,
    end_run,
    ingest_dedupe_key_for_persist,
    map_result_to_cycle,
)


def _result(index: int = 0) -> CycleResult:
    return CycleResult(
        timestamp=datetime(2026, 1, 1, 0, index, tzinfo=timezone.utc),
        cycle_index=index,
        raw_soil_moisture=50.0,
        preprocess_status="valid",
        arx_predicted=49.0,
        x_prior=49.0,
        P_prior=1.1,
        innovation=1.0,
        R=1.0,
        K=0.5,
        x_posterior=49.5,
        P_posterior=0.5,
        cycle_status="ok",
        adaptive_status="R_updated",
        latency_ms=1.2,
    )


@pytest.fixture
def run(db) -> ExperimentRun:
    return ExperimentRun.objects.create(name="live")


def test_dedupe_key_uses_live_timestamp() -> None:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert ingest_dedupe_key_for_persist(7, sample_ts=ts) == "live|7|2026-01-01T00:00:00+00:00"


def test_dedupe_key_requires_timestamp() -> None:
    with pytest.raises(ValueError):
        ingest_dedupe_key_for_persist(7)


@pytest.mark.django_db
def test_map_result_defaults_to_live_online(run: ExperimentRun) -> None:
    cycle = map_result_to_cycle(_result(), run)
    assert cycle.slice_type == PipelineCycle.SliceType.ONLINE
    assert cycle.source_type == PipelineCycle.SourceType.LIVE
    assert cycle.ingest_dedupe_key.startswith(f"live|{run.pk}|")


@pytest.mark.django_db
def test_bulk_save_cycles(run: ExperimentRun) -> None:
    cycles = [map_result_to_cycle(_result(i), run) for i in range(3)]
    assert bulk_save_cycles(cycles) == 3
    assert PipelineCycle.objects.filter(run=run).count() == 3


@pytest.mark.django_db
def test_begin_and_end_run(run: ExperimentRun) -> None:
    begin_run(run)
    assert run.status == ExperimentRun.Status.RUNNING
    end_run(run, ExperimentRun.Status.COMPLETED)
    assert run.status == ExperimentRun.Status.COMPLETED
