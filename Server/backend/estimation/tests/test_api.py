"""Tests for dashboard REST APIs under live-only schema."""

from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from estimation.models import EvaluationSummary, ExperimentRun, Greenhouse, PipelineCycle


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def run(db) -> ExperimentRun:
    user = get_user_model().objects.create_user(username="api-owner")
    greenhouse = Greenhouse.objects.create(owner=user, name="API Greenhouse")
    return ExperimentRun.objects.create(
        name="api-live",
        status=ExperimentRun.Status.RUNNING,
        greenhouse=greenhouse,
    )


def _cycle(run: ExperimentRun, index: int) -> PipelineCycle:
    return PipelineCycle.objects.create(
        run=run,
        greenhouse=run.greenhouse,
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
    assert response.data[0]["greenhouse_id"] == run.greenhouse_id


@pytest.mark.django_db
def test_series_returns_online_cycles(client: APIClient, run: ExperimentRun) -> None:
    _cycle(run, 0)
    response = client.get(f"/api/runs/{run.pk}/series/?slice=online")
    assert response.status_code == 200
    assert response.data["total_cycles"] == 1
    assert response.data["greenhouse_id"] == run.greenhouse_id
    assert response.data["data"][0]["slice_type"] == "online"
    assert response.data["data"][0]["greenhouse_id"] == run.greenhouse_id


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
    assert response.data["greenhouse_id"] == run.greenhouse_id
    assert "online" in response.data["slices"]


@pytest.mark.django_db
def test_authenticated_run_list_is_scoped_to_user(client: APIClient) -> None:
    User = get_user_model()
    owner = User.objects.create_user(username="scope-owner")
    other = User.objects.create_user(username="scope-other")
    greenhouse = Greenhouse.objects.create(owner=owner, name="Owner Greenhouse")
    other_greenhouse = Greenhouse.objects.create(owner=other, name="Other Greenhouse")
    own_run = ExperimentRun.objects.create(name="own", greenhouse=greenhouse)
    ExperimentRun.objects.create(name="other", greenhouse=other_greenhouse)

    client.force_authenticate(user=owner)
    response = client.get("/api/runs/")

    assert response.status_code == 200
    assert [row["id"] for row in response.data] == [own_run.pk]


@pytest.mark.django_db
def test_run_list_filters_by_greenhouse_id(client: APIClient) -> None:
    User = get_user_model()
    owner = User.objects.create_user(username="filter-owner")
    gh1 = Greenhouse.objects.create(owner=owner, name="GH1")
    gh2 = Greenhouse.objects.create(owner=owner, name="GH2")
    run1 = ExperimentRun.objects.create(name="run1", greenhouse=gh1)
    ExperimentRun.objects.create(name="run2", greenhouse=gh2)

    client.force_authenticate(user=owner)
    response = client.get(f"/api/runs/?greenhouse_id={gh1.pk}")

    assert response.status_code == 200
    assert [row["id"] for row in response.data] == [run1.pk]
