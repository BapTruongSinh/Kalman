"""
Tests for the live sensor ingestion endpoint (Task #010).

Coverage
--------
* Happy path: valid sample → 201, correct JSON fields.
* Authentication: missing token → 401; invalid token → 401.
* Run guards: run not found → 404; offline run → 404; pending run → 409;
  completed run → 409.
* Payload validation: missing run_id → 400; missing timestamp → 400;
  non-numeric sensor value → 400.
* Invalid (out-of-range) sensor value still accepted → 201 with
  cycle_status="skipped_no_measurement", preprocess_status="skipped".
* State reconstruction: second sample uses P/R from first cycle.
* Reconnect after error cycle: null kf fields reset state from config.
* No ExperimentConfig → defaults used, still 201.
* preprocess_single unit tests (offline from Django, pure logic).
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from estimation.models import ExperimentConfig, ExperimentRun, PipelineCycle
from estimation.api.ingest import _restore_state, _build_raw_record
from estimation.ingestion.loader import RawRecord
from estimation.ingestion.preprocessor import preprocess_single
from estimation.ingestion.validator import ValidationResult
from estimation.kalman.cycle import KalmanConfig, KalmanState

# ── Test doubles / factories ───────────────────────────────────────────────────

User = get_user_model()

_INGEST_URL = "/api/ingest/samples/"

_VALID_PAYLOAD = {
    "timestamp": "2026-04-14T12:00:00Z",
    "soil_moisture": 45.3,
    "temperature": 22.1,
    "humidity": 65.0,
    "light": 120.0,
    "drip": 0.0,
    "mist": 0.0,
    "fan": 1.0,
}


@pytest.fixture
def device_user(db):
    return User.objects.create_user(username="device01", password="x")


@pytest.fixture
def token(device_user):
    tok, _ = Token.objects.get_or_create(user=device_user)
    return tok.key


@pytest.fixture
def auth_client(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    return client


@pytest.fixture
def live_run(db):
    """Active live ExperimentRun with default ExperimentConfig."""
    run = ExperimentRun.objects.create(
        name="live-test",
        run_type=ExperimentRun.RunType.LIVE,
        status=ExperimentRun.Status.RUNNING,
    )
    ExperimentConfig.objects.create(run=run)
    return run


@pytest.fixture
def payload(live_run):
    return {**_VALID_PAYLOAD, "run_id": live_run.pk}


# ── Authentication ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_unauthenticated_returns_401(live_run):
    client = APIClient()
    resp = client.post(_INGEST_URL, {**_VALID_PAYLOAD, "run_id": live_run.pk}, format="json")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_invalid_token_returns_401(live_run):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
    resp = client.post(_INGEST_URL, {**_VALID_PAYLOAD, "run_id": live_run.pk}, format="json")
    assert resp.status_code == 401


# ── Happy path ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_valid_sample_returns_201(auth_client, payload):
    resp = auth_client.post(_INGEST_URL, payload, format="json")
    assert resp.status_code == 201, resp.data


@pytest.mark.django_db
def test_response_contains_required_fields(auth_client, payload):
    resp = auth_client.post(_INGEST_URL, payload, format="json")
    assert resp.status_code == 201
    body = resp.json()
    for field in ("cycle_index", "preprocess_status", "cycle_status",
                  "adaptive_status", "kf_x_posterior", "kf_innovation"):
        assert field in body, f"Missing field: {field}"


@pytest.mark.django_db
def test_first_sample_has_cycle_index_zero(auth_client, payload):
    resp = auth_client.post(_INGEST_URL, payload, format="json")
    assert resp.json()["cycle_index"] == 0


@pytest.mark.django_db
def test_valid_sample_creates_pipeline_cycle(auth_client, payload, live_run):
    auth_client.post(_INGEST_URL, payload, format="json")
    assert PipelineCycle.objects.filter(run=live_run).count() == 1


@pytest.mark.django_db
def test_stored_cycle_has_live_source_type(auth_client, payload, live_run):
    auth_client.post(_INGEST_URL, payload, format="json")
    cycle = PipelineCycle.objects.get(run=live_run)
    assert cycle.source_type == PipelineCycle.SourceType.LIVE


@pytest.mark.django_db
def test_valid_sample_has_ok_status(auth_client, payload):
    resp = auth_client.post(_INGEST_URL, payload, format="json")
    assert resp.json()["cycle_status"] == "ok"


# ── Run guards ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_unknown_run_id_returns_404(auth_client):
    resp = auth_client.post(
        _INGEST_URL,
        {**_VALID_PAYLOAD, "run_id": 999999},
        format="json",
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_offline_run_returns_404(auth_client, db):
    offline_run = ExperimentRun.objects.create(
        name="offline",
        run_type=ExperimentRun.RunType.OFFLINE_REPLAY,
        status=ExperimentRun.Status.RUNNING,
    )
    resp = auth_client.post(
        _INGEST_URL,
        {**_VALID_PAYLOAD, "run_id": offline_run.pk},
        format="json",
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_pending_live_run_returns_409(auth_client, db):
    run = ExperimentRun.objects.create(
        name="pending-live",
        run_type=ExperimentRun.RunType.LIVE,
        status=ExperimentRun.Status.PENDING,
    )
    resp = auth_client.post(
        _INGEST_URL,
        {**_VALID_PAYLOAD, "run_id": run.pk},
        format="json",
    )
    assert resp.status_code == 409


@pytest.mark.django_db
def test_completed_live_run_returns_409(auth_client, db):
    run = ExperimentRun.objects.create(
        name="completed-live",
        run_type=ExperimentRun.RunType.LIVE,
        status=ExperimentRun.Status.COMPLETED,
    )
    resp = auth_client.post(
        _INGEST_URL,
        {**_VALID_PAYLOAD, "run_id": run.pk},
        format="json",
    )
    assert resp.status_code == 409


# ── Payload validation ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_missing_run_id_returns_400(auth_client):
    resp = auth_client.post(_INGEST_URL, _VALID_PAYLOAD, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_missing_timestamp_returns_400(auth_client, live_run):
    payload = {"run_id": live_run.pk, "soil_moisture": 45.0}
    resp = auth_client.post(_INGEST_URL, payload, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_non_numeric_soil_moisture_returns_400(auth_client, live_run):
    payload = {**_VALID_PAYLOAD, "run_id": live_run.pk, "soil_moisture": "not-a-float"}
    resp = auth_client.post(_INGEST_URL, payload, format="json")
    assert resp.status_code == 400


# ── Invalid sensor values ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_out_of_range_sample_returns_201_with_skipped_status(auth_client, live_run):
    """Out-of-range reading → validation fails → skip policy → still 201."""
    payload = {
        "run_id": live_run.pk,
        "timestamp": "2026-04-14T12:00:00Z",
        "soil_moisture": 9999.0,   # far outside physical range
    }
    resp = auth_client.post(_INGEST_URL, payload, format="json")
    assert resp.status_code == 201
    body = resp.json()
    assert body["preprocess_status"] == "skipped"
    assert body["cycle_status"] == "skipped_no_measurement"


@pytest.mark.django_db
def test_null_soil_moisture_accepted(auth_client, live_run):
    """Null primary channel → Kalman skips measurement update, still 201."""
    payload = {
        "run_id": live_run.pk,
        "timestamp": "2026-04-14T12:00:00Z",
        "soil_moisture": None,
    }
    resp = auth_client.post(_INGEST_URL, payload, format="json")
    assert resp.status_code == 201
    body = resp.json()
    assert body["cycle_status"] == "skipped_no_measurement"


# ── Sequential sample / state reconstruction ──────────────────────────────────


@pytest.mark.django_db
def test_second_sample_has_cycle_index_one(auth_client, payload, live_run):
    auth_client.post(_INGEST_URL, payload, format="json")
    payload2 = {**payload, "timestamp": "2026-04-14T12:00:01Z"}
    resp2 = auth_client.post(_INGEST_URL, payload2, format="json")
    assert resp2.json()["cycle_index"] == 1


@pytest.mark.django_db
def test_state_reconstructed_from_previous_cycle(auth_client, payload, live_run):
    """x_posterior from cycle 0 must differ from x0 config, proving state carried over."""
    r1 = auth_client.post(_INGEST_URL, payload, format="json")
    x_post_1 = r1.json()["kf_x_posterior"]

    payload2 = {**payload, "timestamp": "2026-04-14T12:00:01Z", "soil_moisture": 50.0}
    r2 = auth_client.post(_INGEST_URL, payload2, format="json")
    assert r2.status_code == 201
    # The second posterior should differ from the first, confirming state was loaded
    assert r2.json()["kf_x_posterior"] != x_post_1


# ── Reconnect / error cycle recovery ──────────────────────────────────────────


@pytest.mark.django_db
def test_reconnect_after_error_cycle_resets_state(auth_client, payload, live_run):
    """If last cycle has null kf fields (error), state resets from config → still 201."""
    # Manually insert an error cycle with null Kalman fields
    PipelineCycle.objects.create(
        run=live_run,
        sample_ts="2026-04-14T11:59:00Z",
        cycle_index=0,
        slice_type=PipelineCycle.SliceType.TRAIN,
        source_type=PipelineCycle.SourceType.LIVE,
        cycle_status=PipelineCycle.CycleStatus.ERROR,
        adaptive_status=PipelineCycle.AdaptiveStatus.SKIPPED,
        # kf fields intentionally left as NULL (None)
        kf_x_posterior=None,
        kf_P_posterior=None,
        kf_R=None,
    )

    payload2 = {**payload, "timestamp": "2026-04-14T12:00:00Z"}
    resp = auth_client.post(_INGEST_URL, payload2, format="json")
    assert resp.status_code == 201
    assert resp.json()["cycle_index"] == 1


# ── No ExperimentConfig ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_missing_experiment_config_uses_defaults(auth_client, db):
    """Run without a config snapshot falls back to ADR-003 defaults."""
    run = ExperimentRun.objects.create(
        name="no-config-live",
        run_type=ExperimentRun.RunType.LIVE,
        status=ExperimentRun.Status.RUNNING,
    )
    # Intentionally do NOT create ExperimentConfig
    payload = {**_VALID_PAYLOAD, "run_id": run.pk}
    resp = auth_client.post(_INGEST_URL, payload, format="json")
    assert resp.status_code == 201


# ── preprocess_single unit tests (pure, no DB) ────────────────────────────────


def _make_raw(sm: float | None = 45.0) -> RawRecord:
    from datetime import datetime, timezone
    return RawRecord(
        timestamp=datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc),
        soil_moisture=sm,
        temperature=22.0,
        humidity=60.0,
        light=100.0,
        drip=0.0,
        mist=0.0,
        fan=1.0,
        row_index=0,
    )


def test_preprocess_single_valid_record():
    raw = _make_raw(sm=45.0)
    vr = ValidationResult(is_valid=True, status="valid")
    processed = preprocess_single(raw, vr)
    assert processed.preprocess_status == "valid"
    assert processed.soil_moisture == 45.0


def test_preprocess_single_invalid_record_skips_all_fields():
    raw = _make_raw(sm=9999.0)
    vr = ValidationResult(is_valid=False, status="out_of_range", reason="too high")
    processed = preprocess_single(raw, vr)
    assert processed.preprocess_status == "skipped"
    assert processed.soil_moisture is None
    assert processed.temperature is None
    assert processed.humidity is None


def test_preprocess_single_preserves_raw_reference():
    raw = _make_raw()
    vr = ValidationResult(is_valid=True, status="valid")
    processed = preprocess_single(raw, vr)
    assert processed.raw is raw
    assert processed.validation is vr


# ── _restore_state unit tests (pure, no DB) ───────────────────────────────────


def test_restore_state_no_cycles_returns_config_defaults():
    config = KalmanConfig(x0=30.0, P0=2.0, R0=1.5)
    state, idx = _restore_state(None, config)
    assert idx == 0
    assert state.x_post == 30.0
    assert state.P_post == 2.0
    assert state.R == 1.5
    assert state.step == 0


def test_restore_state_from_valid_last_cycle():
    config = KalmanConfig()
    # Minimal stand-in for PipelineCycle (duck-typed)
    class _FakeCycle:
        cycle_index = 4
        run_id = 1
        kf_x_posterior = 42.5
        kf_P_posterior = 0.8
        kf_R = 1.2

    state, idx = _restore_state(_FakeCycle(), config)
    assert idx == 5
    assert state.x_post == 42.5
    assert state.P_post == 0.8
    assert state.R == 1.2
    assert state.step == 5


def test_restore_state_null_kf_fields_resets_from_config():
    config = KalmanConfig(x0=20.0)

    class _FaultyCycle:
        cycle_index = 3
        run_id = 1
        kf_x_posterior = None
        kf_P_posterior = None
        kf_R = None

    state, idx = _restore_state(_FaultyCycle(), config)
    assert idx == 4  # next index still advances
    assert state.x_post == 20.0  # reset from config


def test_restore_state_non_positive_covariance_resets():
    config = KalmanConfig()

    class _BadCycle:
        cycle_index = 2
        run_id = 1
        kf_x_posterior = 40.0
        kf_P_posterior = -0.1   # invalid
        kf_R = 1.0

    state, idx = _restore_state(_BadCycle(), config)
    assert state.x_post == config.x0  # reset
    assert idx == 3
