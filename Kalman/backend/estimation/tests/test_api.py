"""Tests for dashboard REST APIs under live-only schema."""

from datetime import datetime, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from estimation.models import EvaluationSummary, ExperimentRun, PipelineCycle


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def run(db) -> ExperimentRun:
    return ExperimentRun.objects.create(name="api-live", status=ExperimentRun.Status.RUNNING)


def _cycle(run: ExperimentRun, index: int) -> PipelineCycle:
    return PipelineCycle.objects.create(
        run=run,
        sample_ts=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index),
        cycle_index=index,
        slice_type=PipelineCycle.SliceType.ONLINE,
        source_type=PipelineCycle.SourceType.LIVE,
        ingest_dedupe_key=f"live|{run.pk}|{index}",
        raw_soil_moisture=50.0 + index,
        arx_predicted=49.0 + index,
        kf_x_posterior=49.5 + index,
        kf_R=1.0,
        cycle_status="ok",
        adaptive_status="R_updated",
    )


@pytest.mark.django_db
def test_run_list_returns_live_runs(client: APIClient, run: ExperimentRun) -> None:
    response = client.get("/api/runs/")
    assert response.status_code == 200
    assert response.data[0]["run_type"] == "live"


@pytest.mark.django_db
def test_series_returns_online_cycles(client: APIClient, run: ExperimentRun) -> None:
    _cycle(run, 0)
    response = client.get(f"/api/runs/{run.pk}/series/?slice=online")
    assert response.status_code == 200
    assert response.data["total_cycles"] == 1
    assert response.data["data"][0]["slice_type"] == "online"


@pytest.mark.django_db
def test_series_rejects_old_slice_names(client: APIClient, run: ExperimentRun) -> None:
    response = client.get(f"/api/runs/{run.pk}/series/?slice=test")
    assert response.status_code == 400


@pytest.mark.django_db
def test_metrics_returns_online_summary(client: APIClient, run: ExperimentRun) -> None:
    EvaluationSummary.objects.create(
        run=run,
        slice_type=EvaluationSummary.SliceType.ONLINE,
        n_samples=2,
        n_valid=2,
    )
    response = client.get(f"/api/runs/{run.pk}/metrics/")
    assert response.status_code == 200
    assert "online" in response.data["slices"]
