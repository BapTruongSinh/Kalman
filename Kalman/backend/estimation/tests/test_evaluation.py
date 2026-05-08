"""Tests for online evaluation metrics."""

from datetime import datetime, timedelta, timezone

import pytest

from estimation.evaluation import compute_metrics, evaluate_online, evaluate_slice
from estimation.models import EvaluationSummary, ExperimentRun, PipelineCycle


def _row(i: int) -> dict:
    raw = [50.0, 52.0, 51.0, 55.0, 54.0][i]
    return {
        "raw_soil_moisture": raw,
        "arx_predicted": raw - 0.2,
        "kf_x_posterior": raw - 0.1,
        "kf_innovation": 0.2,
        "kf_R": 1.0,
        "kf_P_posterior": 0.5,
        "cycle_status": "ok",
        "adaptive_status": "R_updated",
        "latency_ms": 2.0,
    }


@pytest.fixture
def run(db) -> ExperimentRun:
    return ExperimentRun.objects.create(name="eval-live", status=ExperimentRun.Status.RUNNING)


def test_compute_metrics_online_rows() -> None:
    metrics = compute_metrics([_row(i) for i in range(5)])
    assert metrics.n_samples == 5
    assert metrics.n_valid == 5
    assert metrics.rmse_filtered is not None
    assert metrics.variance_reduction is not None


@pytest.mark.django_db
def test_evaluate_online_persists_summary(run: ExperimentRun) -> None:
    for i in range(5):
        PipelineCycle.objects.create(
            run=run,
            sample_ts=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i),
            cycle_index=i,
            slice_type=PipelineCycle.SliceType.ONLINE,
            source_type=PipelineCycle.SourceType.LIVE,
            ingest_dedupe_key=f"live|{run.pk}|{i}",
            raw_soil_moisture=50.0 + i,
            arx_predicted=49.8 + i,
            kf_x_posterior=50.1 + i * 0.9,
            kf_innovation=0.1,
            kf_R=1.0,
            kf_P_posterior=0.5,
            cycle_status="ok",
            adaptive_status="R_updated",
            latency_ms=1.0,
        )

    summary = evaluate_online(run.pk)
    assert summary.slice_type == EvaluationSummary.SliceType.ONLINE
    assert summary.n_samples == 5
    assert EvaluationSummary.objects.filter(run=run, slice_type="online").count() == 1


@pytest.mark.django_db
def test_evaluate_slice_rejects_non_online(run: ExperimentRun) -> None:
    with pytest.raises(ValueError, match="online"):
        evaluate_slice(run.pk, "test")
