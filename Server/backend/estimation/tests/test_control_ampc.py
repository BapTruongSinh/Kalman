"""Tests for Django AMPC online integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone as django_timezone
from mpc.actuator import ActuatorResult
from rest_framework.test import APIClient

import estimation.control.service as control_service
from estimation.control.bias import build_bias_state
from estimation.control.config import profile_to_controller_config
from estimation.control.service import run_ampc_for_greenhouse, used_today_pump_seconds
from estimation.control.state_source import (
    StateUnavailableError,
    history_for_greenhouse,
    latest_state_cycle_for_greenhouse,
    validate_cycle_fresh,
)
from estimation.models import (
    AMPCRecommendation,
    ExperimentRun,
    Greenhouse,
    GreenhouseControlProfile,
    PipelineCycle,
)

NOW = datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)


class FakePlantModel:
    min_history_len = 3

    def predict_next(
        self,
        history,
        *,
        pump_seconds,
        step_seconds,
        disturbance=None,
    ) -> float:
        return history[-1].soil_moisture + 0.05 + pump_seconds / 300.0


class FakeActuator:
    def __init__(self, *, executed: bool = True) -> None:
        self.executed = executed
        self.calls = []

    def send(self, command):
        self.calls.append(command)
        if self.executed:
            return ActuatorResult(
                executed=True,
                status="sent",
                command=command,
                http_status_code=200,
            )
        return ActuatorResult(
            executed=False,
            status="http_error",
            command=command,
            http_status_code=503,
            alert="actuator_http_failure",
            error="HTTP 503",
        )


class RaisingActuator:
    def send(self, command):
        raise TimeoutError("network timeout")


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user(username="ampc-owner")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(username="ampc-other")


@pytest.fixture
def greenhouse(owner) -> Greenhouse:
    return Greenhouse.objects.create(owner=owner, name="AMPC Greenhouse")


@pytest.fixture
def run(greenhouse) -> ExperimentRun:
    return ExperimentRun.objects.create(
        name="ampc-live",
        status=ExperimentRun.Status.RUNNING,
        greenhouse=greenhouse,
    )


@pytest.fixture
def auth_client(owner) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


def _cycle(
    run: ExperimentRun,
    index: int,
    *,
    sample_ts: datetime | None = None,
    status: str = PipelineCycle.CycleStatus.OK,
    preprocess_status: str = PipelineCycle.PreprocessStatus.VALID,
    include_disturbances: bool = True,
    soil: float = 54.0,
    arx: float | None = None,
) -> PipelineCycle:
    ts = sample_ts or (NOW - timedelta(minutes=10 - index))
    return PipelineCycle.objects.create(
        run=run,
        greenhouse=run.greenhouse,
        sample_ts=ts,
        cycle_index=index,
        slice_type=PipelineCycle.SliceType.ONLINE,
        source_type=PipelineCycle.SourceType.LIVE,
        ingest_dedupe_key=f"live|{run.pk}|{index}|{ts.isoformat()}",
        raw_soil_moisture=soil,
        raw_temperature=24.0 if include_disturbances else None,
        raw_humidity=60.0 if include_disturbances else None,
        raw_light=120.0 if include_disturbances else None,
        raw_drip=0.0,
        raw_mist=0.0,
        raw_fan=0.0,
        arx_predicted=soil - 1.0 if arx is None else arx,
        kf_x_posterior=soil,
        kf_R=1.0,
        cycle_status=status,
        preprocess_status=preprocess_status,
        adaptive_status=PipelineCycle.AdaptiveStatus.R_UPDATED,
    )


def _seed_history(run: ExperimentRun, *, count: int = 3) -> None:
    for index in range(count):
        _cycle(run, index, soil=54.0 + index)


def _seed_fresh_history(run: ExperimentRun, *, count: int = 3) -> None:
    base_ts = django_timezone.now()
    for index in range(count):
        sample_ts = base_ts - timedelta(minutes=count - index - 1)
        _cycle(run, index, sample_ts=sample_ts, soil=54.0 + index)


def _patch_fake_plant(monkeypatch) -> None:
    monkeypatch.setattr(
        control_service.ARXPlantModel,
        "load_artifact",
        staticmethod(lambda *args, **kwargs: FakePlantModel()),
    )


@pytest.mark.django_db
def test_profile_to_controller_config_maps_defaults(greenhouse: Greenhouse) -> None:
    profile = GreenhouseControlProfile.objects.create(greenhouse=greenhouse)
    config = profile_to_controller_config(profile)

    assert config.step_seconds == 300
    assert config.horizon_steps == 12
    assert config.target_band.low == 55.0
    assert config.target_band.high == 65.0
    assert config.pump.max_seconds == 300.0
    assert config.adaptive.enabled is True
    assert config.actuator.enabled is False


@pytest.mark.django_db
def test_profile_to_controller_config_rejects_unsafe_actuator_url(
    greenhouse: Greenhouse,
) -> None:
    profile = GreenhouseControlProfile.objects.create(
        greenhouse=greenhouse,
        actuator_enabled=True,
        actuator_url="http://127.0.0.1/pump",
        actuator_bearer_token_env="PUMP_TOKEN",
    )

    with pytest.raises(ValueError, match="actuator_url_host_not_allowed"):
        profile_to_controller_config(profile)


@pytest.mark.django_db
def test_latest_state_and_history_use_same_greenhouse(
    run: ExperimentRun,
    other_user,
) -> None:
    _seed_history(run)
    other_greenhouse = Greenhouse.objects.create(owner=other_user, name="Other")
    other_run = ExperimentRun.objects.create(name="other", greenhouse=other_greenhouse)
    _cycle(other_run, 0, soil=99.0)

    latest = latest_state_cycle_for_greenhouse(run.greenhouse_id)
    history = history_for_greenhouse(run.greenhouse_id, limit=3)

    assert latest.run_id == run.pk
    assert latest.kf_x_posterior == 56.0
    assert [row.soil_moisture for row in history] == [54.0, 55.0, 56.0]


@pytest.mark.django_db
def test_state_lookup_ignores_invalid_cycles(run: ExperimentRun) -> None:
    _cycle(run, 0, status=PipelineCycle.CycleStatus.ERROR, soil=90.0)
    _cycle(run, 1, preprocess_status=PipelineCycle.PreprocessStatus.SKIPPED, soil=91.0)
    _cycle(run, 2, include_disturbances=False, soil=92.0)

    assert latest_state_cycle_for_greenhouse(run.greenhouse_id) is None


@pytest.mark.django_db
def test_validate_cycle_fresh_rejects_stale_and_future(run: ExperimentRun) -> None:
    profile = GreenhouseControlProfile.objects.create(greenhouse=run.greenhouse)
    config = profile_to_controller_config(profile)
    stale = _cycle(run, 0, sample_ts=NOW - timedelta(hours=2))
    future = _cycle(run, 1, sample_ts=NOW + timedelta(minutes=2))

    with pytest.raises(StateUnavailableError, match="stale_sample"):
        validate_cycle_fresh(stale, config=config, now=NOW)
    with pytest.raises(StateUnavailableError, match="future_sample"):
        validate_cycle_fresh(future, config=config, now=NOW)


@pytest.mark.django_db
def test_bias_builder_uses_recent_clipped_residuals(run: ExperimentRun) -> None:
    _cycle(run, 0, soil=50.0, arx=40.0)
    _cycle(run, 1, soil=51.0, arx=50.0)
    profile = GreenhouseControlProfile.objects.create(
        greenhouse=run.greenhouse,
        adaptive_max_abs_bias=2.0,
        adaptive_bias_window=2,
    )
    config = profile_to_controller_config(profile)

    bias = build_bias_state(
        greenhouse_id=run.greenhouse_id,
        adaptive_config=config.adaptive,
    )

    assert bias.residuals == (2.0, 1.0)
    assert bias.current_bias == pytest.approx(1.5)


@pytest.mark.django_db
def test_used_today_pump_seconds_scopes_greenhouse_and_day(
    greenhouse: Greenhouse,
    other_user,
) -> None:
    other_greenhouse = Greenhouse.objects.create(owner=other_user, name="Other")
    today = AMPCRecommendation.objects.create(
        greenhouse=greenhouse,
        pump_seconds=30.0,
        reason="today",
    )
    yesterday = AMPCRecommendation.objects.create(
        greenhouse=greenhouse,
        pump_seconds=90.0,
        reason="old",
    )
    AMPCRecommendation.objects.create(
        greenhouse=other_greenhouse,
        pump_seconds=100.0,
        reason="other",
    )
    AMPCRecommendation.objects.filter(pk=today.pk).update(created_at=NOW)
    AMPCRecommendation.objects.filter(pk=yesterday.pk).update(
        created_at=NOW - timedelta(days=1)
    )

    assert used_today_pump_seconds(greenhouse=greenhouse, now=NOW) == 30.0


@pytest.mark.django_db
def test_ampc_service_happy_path_persists_recommendation(
    owner,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    _patch_fake_plant(monkeypatch)
    _seed_history(run)

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
        beam_width=4,
    )

    assert rec.greenhouse_id == run.greenhouse_id
    assert rec.state_cycle_id is not None
    assert rec.safety_status == AMPCRecommendation.SafetyStatus.SAFE
    assert len(rec.predicted_soil_moisture_json) == 12
    assert rec.bias_correction == pytest.approx(1.0)
    assert rec.actuator_status == "disabled"


@pytest.mark.django_db
def test_ampc_service_missing_state_persists_fail_closed(
    owner,
    greenhouse: Greenhouse,
    monkeypatch,
) -> None:
    _patch_fake_plant(monkeypatch)

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=greenhouse.pk,
        now=NOW,
    )

    assert rec.pump_seconds == 0.0
    assert rec.safety_status == AMPCRecommendation.SafetyStatus.PUMP_OFF_FAILSAFE
    assert rec.reason == "state_unavailable"
    assert rec.state_cycle_id is None


@pytest.mark.django_db
def test_ampc_service_insufficient_history_persists_fail_closed(
    owner,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    _patch_fake_plant(monkeypatch)
    _seed_history(run, count=2)

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
    )

    assert rec.pump_seconds == 0.0
    assert rec.safety_status == AMPCRecommendation.SafetyStatus.MODEL_ERROR
    assert rec.reason == "history_too_short"


@pytest.mark.django_db
def test_ampc_service_model_load_error_persists_fail_closed(
    owner,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    def _raise(*args, **kwargs):
        raise FileNotFoundError("missing artifact")

    monkeypatch.setattr(
        control_service.ARXPlantModel,
        "load_artifact",
        staticmethod(_raise),
    )
    _seed_history(run)

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
    )

    assert rec.pump_seconds == 0.0
    assert rec.safety_status == AMPCRecommendation.SafetyStatus.MODEL_ERROR
    assert rec.reason.startswith("model_load_error")


@pytest.mark.django_db
def test_ampc_service_solver_exception_persists_fail_closed(
    owner,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    class RaisingSolver:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def recommend(self, *args, **kwargs):
            raise RuntimeError("solver boom")

    _patch_fake_plant(monkeypatch)
    _seed_history(run)
    monkeypatch.setattr(control_service, "GridShootingSolver", RaisingSolver)

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
    )

    assert rec.pump_seconds == 0.0
    assert rec.safety_status == AMPCRecommendation.SafetyStatus.SOLVER_ERROR
    assert rec.reason == "solver_error:RuntimeError"


@pytest.mark.django_db
def test_unsafe_recommendation_does_not_call_actuator(
    owner,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    class RaisingSolver:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def recommend(self, *args, **kwargs):
            raise RuntimeError("solver boom")

    _patch_fake_plant(monkeypatch)
    _seed_history(run)
    monkeypatch.setattr(control_service, "GridShootingSolver", RaisingSolver)
    monkeypatch.setenv("TEST_ACTUATOR_TOKEN", "token")
    GreenhouseControlProfile.objects.create(
        greenhouse=run.greenhouse,
        actuator_enabled=True,
        actuator_url="https://actuator.example/command",
        actuator_bearer_token_env="TEST_ACTUATOR_TOKEN",
    )
    fake = FakeActuator()

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
        beam_width=4,
        actuator_client=fake,
    )

    assert fake.calls == []
    assert rec.pump_seconds == 0.0
    assert rec.safety_status == AMPCRecommendation.SafetyStatus.SOLVER_ERROR
    assert rec.actuator_executed is False
    assert rec.actuator_status == "not_called"


@pytest.mark.django_db
def test_actuator_disabled_does_not_call_client(owner, run: ExperimentRun, monkeypatch) -> None:
    _patch_fake_plant(monkeypatch)
    _seed_history(run)
    fake = FakeActuator()

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
        beam_width=4,
        actuator_client=fake,
    )

    assert fake.calls == []
    assert rec.actuator_status == "disabled"


@pytest.mark.django_db
def test_fake_actuator_cannot_bypass_invalid_config(
    owner,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    _patch_fake_plant(monkeypatch)
    _seed_history(run)
    GreenhouseControlProfile.objects.create(
        greenhouse=run.greenhouse,
        actuator_enabled=True,
    )
    fake = FakeActuator()

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
        beam_width=4,
        actuator_client=fake,
    )

    assert fake.calls == []
    assert rec.pump_seconds == 0.0
    assert rec.safety_status == AMPCRecommendation.SafetyStatus.CONFIG_ERROR
    assert rec.actuator_status == "config_error"


@pytest.mark.django_db
def test_actuator_enabled_with_fake_client_records_execution(
    owner,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    _patch_fake_plant(monkeypatch)
    _seed_history(run)
    monkeypatch.setenv("TEST_ACTUATOR_TOKEN", "token")
    GreenhouseControlProfile.objects.create(
        greenhouse=run.greenhouse,
        actuator_enabled=True,
        actuator_url="https://actuator.example/command",
        actuator_bearer_token_env="TEST_ACTUATOR_TOKEN",
    )
    fake = FakeActuator()

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
        beam_width=4,
        actuator_client=fake,
        command_id_factory=lambda: "cmd-1",
    )

    assert len(fake.calls) == 1
    assert rec.actuator_executed is True
    assert rec.actuator_status == "sent"
    assert rec.actuator_command_json["command_id"] == "cmd-1"


@pytest.mark.django_db
def test_actuator_http_failure_records_fail_closed(
    owner,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    _patch_fake_plant(monkeypatch)
    _seed_history(run)
    monkeypatch.setenv("TEST_ACTUATOR_TOKEN", "token")
    GreenhouseControlProfile.objects.create(
        greenhouse=run.greenhouse,
        actuator_enabled=True,
        actuator_url="https://actuator.example/command",
        actuator_bearer_token_env="TEST_ACTUATOR_TOKEN",
    )

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
        beam_width=4,
        actuator_client=FakeActuator(executed=False),
    )

    assert rec.pump_seconds == 0.0
    assert rec.safety_status == AMPCRecommendation.SafetyStatus.ACTUATOR_ERROR
    assert rec.actuator_status == "http_error"
    assert rec.actuator_error == "HTTP 503"


@pytest.mark.django_db
def test_actuator_send_exception_records_fail_closed(
    owner,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    _patch_fake_plant(monkeypatch)
    _seed_history(run)
    monkeypatch.setenv("TEST_ACTUATOR_TOKEN", "token")
    GreenhouseControlProfile.objects.create(
        greenhouse=run.greenhouse,
        actuator_enabled=True,
        actuator_url="https://actuator.example/command",
        actuator_bearer_token_env="TEST_ACTUATOR_TOKEN",
    )

    rec = run_ampc_for_greenhouse(
        user=owner,
        greenhouse_id=run.greenhouse_id,
        now=NOW,
        beam_width=4,
        actuator_client=RaisingActuator(),
    )

    assert rec.pump_seconds == 0.0
    assert rec.safety_status == AMPCRecommendation.SafetyStatus.ACTUATOR_ERROR
    assert rec.actuator_status == "http_error"
    assert rec.actuator_alert == "actuator_http_failure"
    assert rec.actuator_error == "TimeoutError"


@pytest.mark.django_db
def test_ampc_post_requires_auth(client: APIClient, greenhouse: Greenhouse) -> None:
    response = client.post(
        f"/api/greenhouses/{greenhouse.pk}/ampc/recommendations/",
        {},
        format="json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_ampc_post_cross_user_returns_404_no_recommendation(
    other_user,
    auth_client: APIClient,
) -> None:
    other_greenhouse = Greenhouse.objects.create(owner=other_user, name="Other")

    response = auth_client.post(
        f"/api/greenhouses/{other_greenhouse.pk}/ampc/recommendations/",
        {},
        format="json",
    )

    assert response.status_code == 404
    assert AMPCRecommendation.objects.count() == 0


@pytest.mark.django_db
def test_ampc_post_owner_creates_recommendation(
    auth_client: APIClient,
    run: ExperimentRun,
    monkeypatch,
) -> None:
    _patch_fake_plant(monkeypatch)
    _seed_fresh_history(run)

    response = auth_client.post(
        f"/api/greenhouses/{run.greenhouse_id}/ampc/recommendations/",
        {},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["success"] is True
    assert response.data["data"]["greenhouse_id"] == run.greenhouse_id
    assert response.data["data"]["safety_status"] == "safe"
    assert "config_snapshot_json" not in response.data["data"]
    assert "actuator_bearer_token_env" not in str(response.data)
    assert AMPCRecommendation.objects.filter(greenhouse=run.greenhouse).count() == 1


@pytest.mark.django_db
def test_ampc_post_inactive_greenhouse_returns_403(
    auth_client: APIClient,
    greenhouse: Greenhouse,
) -> None:
    greenhouse.is_active = False
    greenhouse.save(update_fields=["is_active"])

    response = auth_client.post(
        f"/api/greenhouses/{greenhouse.pk}/ampc/recommendations/",
        {},
        format="json",
    )

    assert response.status_code == 403
    assert response.data["success"] is False
    assert AMPCRecommendation.objects.count() == 0


@pytest.mark.django_db
def test_ampc_post_no_state_returns_fail_closed_data(
    auth_client: APIClient,
    greenhouse: Greenhouse,
) -> None:
    response = auth_client.post(
        f"/api/greenhouses/{greenhouse.pk}/ampc/recommendations/",
        {},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["pump_seconds"] == 0.0
    assert response.data["data"]["safety_status"] == "pump_off_failsafe"
    assert response.data["data"]["reason"] == "state_unavailable"


@pytest.mark.django_db
def test_latest_recommendation_endpoint_scopes_to_owner(
    auth_client: APIClient,
    greenhouse: Greenhouse,
) -> None:
    older = AMPCRecommendation.objects.create(greenhouse=greenhouse, reason="old")
    latest = AMPCRecommendation.objects.create(
        greenhouse=greenhouse,
        reason="new",
        pump_seconds=10.0,
    )

    response = auth_client.get(
        f"/api/greenhouses/{greenhouse.pk}/ampc/recommendations/latest/"
    )

    assert response.status_code == 200
    assert response.data["data"]["id"] == latest.pk
    assert response.data["data"]["id"] != older.pk


@pytest.mark.django_db
def test_profile_get_creates_default_profile(
    auth_client: APIClient,
    greenhouse: Greenhouse,
) -> None:
    response = auth_client.get(f"/api/greenhouses/{greenhouse.pk}/control-profile/")

    assert response.status_code == 200
    assert response.data["data"]["greenhouse_id"] == greenhouse.pk
    assert response.data["data"]["target_low"] == 55.0
    assert GreenhouseControlProfile.objects.filter(greenhouse=greenhouse).exists()


@pytest.mark.django_db
def test_profile_patch_updates_allowed_fields_only(
    auth_client: APIClient,
    greenhouse: Greenhouse,
) -> None:
    profile = GreenhouseControlProfile.objects.create(greenhouse=greenhouse)

    response = auth_client.patch(
        f"/api/greenhouses/{greenhouse.pk}/control-profile/",
        {
            "crop_name": "tomato",
            "target_low": 54.0,
            "target_high": 64.0,
            "actuator_bearer_token_env": "LEAK",
        },
        format="json",
    )

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.crop_name == "tomato"
    assert profile.target_low == 54.0
    assert profile.actuator_bearer_token_env is None
    assert "actuator_bearer_token_env" not in str(response.data)


@pytest.mark.django_db
def test_profile_patch_rejects_invalid_target_band(
    auth_client: APIClient,
    greenhouse: Greenhouse,
) -> None:
    GreenhouseControlProfile.objects.create(greenhouse=greenhouse)

    response = auth_client.patch(
        f"/api/greenhouses/{greenhouse.pk}/control-profile/",
        {"target_low": 70.0, "target_high": 60.0},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["success"] is False
    assert response.data["error"]["code"] == "invalid_profile"


@pytest.mark.django_db
def test_profile_patch_rejects_nonnumeric_target_without_500(
    auth_client: APIClient,
    greenhouse: Greenhouse,
) -> None:
    GreenhouseControlProfile.objects.create(greenhouse=greenhouse)

    response = auth_client.patch(
        f"/api/greenhouses/{greenhouse.pk}/control-profile/",
        {"target_low": "not-a-number"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["success"] is False
    assert response.data["error"]["code"] == "invalid_profile"
