"""
Tests for the estimation REST API endpoints.

Uses pytest-django and the DRF APIClient.
Run with:  pytest estimation/tests/test_api.py -q --create-db
"""

import datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from estimation.models import (
    ExperimentConfig,
    ExperimentRun,
    PipelineCycle,
)
from estimation.pipeline.store import ingest_dedupe_key_for_persist


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def run(db) -> ExperimentRun:
    return ExperimentRun.objects.create(
        name="test-api-run",
        run_type=ExperimentRun.RunType.OFFLINE_REPLAY,
        status=ExperimentRun.Status.COMPLETED,
    )


def _ts(offset_seconds: int = 0) -> datetime.datetime:
    base = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    return base + datetime.timedelta(seconds=offset_seconds)


def _cycle(run: ExperimentRun, index: int, slice_type: str = "test") -> PipelineCycle:
    ts = _ts(index)
    dedupe = ingest_dedupe_key_for_persist(
        run.pk,
        PipelineCycle.SourceType.CSV_REPLAY,
        cycle_index=index,
        sample_ts=ts,
    )
    return PipelineCycle.objects.create(
        run=run,
        cycle_index=index,
        sample_ts=ts,
        ingest_dedupe_key=dedupe,
        slice_type=slice_type,
        raw_soil_moisture=50.0 + index * 0.1,
        arx_predicted=50.1 + index * 0.1,
        kf_x_posterior=50.05 + index * 0.1,
        kf_innovation=0.1,
        kf_R=1.0,
        latency_ms=0.5,
        cycle_status=PipelineCycle.CycleStatus.OK,
        adaptive_status=PipelineCycle.AdaptiveStatus.R_UPDATED,
    )

# ---------------------------------------------------------------------------
# Run list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunListView:
    def test_empty_returns_empty_list(self, client):
        resp = client.get("/api/runs/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_run_fields(self, client, run):
        resp = client.get("/api/runs/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        row = data[0]
        assert row["id"] == run.pk
        assert row["name"] == "test-api-run"
        assert row["status"] == "completed"
        assert row["run_type"] == "offline_replay"
        assert "created_at" in row

    def test_ordered_newest_first(self, client, db):
        r1 = ExperimentRun.objects.create(name="old", status="completed")
        r2 = ExperimentRun.objects.create(name="new", status="completed")
        # Ensure deterministic ordering by back-dating r1
        ExperimentRun.objects.filter(pk=r1.pk).update(
            created_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
        )
        data = client.get("/api/runs/").json()
        ids = [d["id"] for d in data]
        assert ids.index(r2.pk) < ids.index(r1.pk)


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunSeriesView:
    def test_404_for_missing_run(self, client):
        resp = client.get("/api/runs/99999/series/")
        assert resp.status_code == 404

    def test_empty_run_returns_empty_data(self, client, run):
        resp = client.get(f"/api/runs/{run.pk}/series/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == run.pk
        assert body["total_cycles"] == 0
        assert body["data"] == []

    def test_returns_cycles(self, client, run):
        for i in range(5):
            _cycle(run, i, "test")
        resp = client.get(f"/api/runs/{run.pk}/series/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_cycles"] == 5
        assert len(body["data"]) == 5

    def test_series_fields_present(self, client, run):
        _cycle(run, 0)
        row = client.get(f"/api/runs/{run.pk}/series/").json()["data"][0]
        required = {
            "cycle_index",
            "slice_type",
            "sample_ts",
            "raw_soil_moisture",
            "arx_predicted",
            "kf_x_posterior",
            "kf_innovation",
            "kf_R",
            "latency_ms",
            "preprocess_status",
            "cycle_status",
            "adaptive_status",
        }
        assert required.issubset(row.keys())

    def test_filter_by_slice_type(self, client, run):
        for i in range(3):
            _cycle(run, i, "train")
        for i in range(3, 6):
            _cycle(run, i, "test")
        resp = client.get(f"/api/runs/{run.pk}/series/?slice=train")
        data = resp.json()["data"]
        assert all(d["slice_type"] == "train" for d in data)
        assert len(data) == 3

    def test_invalid_slice_returns_400(self, client, run):
        for i in range(4):
            _cycle(run, i)
        resp = client.get(f"/api/runs/{run.pk}/series/?slice=bogus")
        assert resp.status_code == 400
        assert "slice" in resp.json().get("error", "")

    def test_limit_stride_product_too_large_returns_400(self, client, run):
        resp = client.get(f"/api/runs/{run.pk}/series/?limit=10000&stride=1000")
        assert resp.status_code == 400
        assert "limit * stride" in resp.json().get("error", "")

    def test_limit_param_respected(self, client, run):
        for i in range(10):
            _cycle(run, i)
        resp = client.get(f"/api/runs/{run.pk}/series/?limit=3")
        body = resp.json()
        assert body["total_cycles"] == 10
        assert len(body["data"]) == 3

    def test_stride_downsamples(self, client, run):
        for i in range(9):
            _cycle(run, i)
        resp = client.get(f"/api/runs/{run.pk}/series/?stride=3")
        body = resp.json()
        assert body["total_cycles"] == 9
        returned = body["returned"]
        assert returned == 3

    def test_data_ordered_by_cycle_index(self, client, run):
        for i in [4, 1, 3, 0, 2]:
            _cycle(run, i)
        data = client.get(f"/api/runs/{run.pk}/series/").json()["data"]
        indices = [d["cycle_index"] for d in data]
        assert indices == sorted(indices)

    # ---- Bad query-param validation (must return 400, not 500) -------------

    def test_non_integer_limit_returns_400(self, client, run):
        resp = client.get(f"/api/runs/{run.pk}/series/?limit=abc")
        assert resp.status_code == 400
        assert "limit" in resp.json().get("error", "")

    def test_negative_limit_returns_400(self, client, run):
        resp = client.get(f"/api/runs/{run.pk}/series/?limit=-1")
        assert resp.status_code == 400

    def test_zero_limit_returns_400(self, client, run):
        resp = client.get(f"/api/runs/{run.pk}/series/?limit=0")
        assert resp.status_code == 400

    def test_non_integer_stride_returns_400(self, client, run):
        resp = client.get(f"/api/runs/{run.pk}/series/?stride=abc")
        assert resp.status_code == 400
        assert "stride" in resp.json().get("error", "")

    def test_negative_stride_returns_400(self, client, run):
        resp = client.get(f"/api/runs/{run.pk}/series/?stride=-5")
        assert resp.status_code == 400

    def test_limit_clamped_to_max(self, client, run):
        for i in range(5):
            _cycle(run, i)
        resp = client.get(f"/api/runs/{run.pk}/series/?limit=999999")
        assert resp.status_code == 200
        assert resp.json()["total_cycles"] == 5

    def test_stride_bounds_id_scan(self, client, run):
        """stride=large + limit=1 should return at most 1 cycle, not error."""
        for i in range(20):
            _cycle(run, i)
        resp = client.get(f"/api/runs/{run.pk}/series/?stride=10&limit=1")
        assert resp.status_code == 200
        assert resp.json()["returned"] <= 1


