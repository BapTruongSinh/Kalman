"""Django service for running online AMPC by greenhouse."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone as django_timezone
from mpc.actuator import ActuatorCommand, ActuatorResult, HTTPActuatorClient
from mpc.adaptive import BiasCorrectedPlantModel
from mpc.config import ControllerConfig
from mpc.plant import ARXPlantModel
from mpc.solver import GridShootingSolver
from mpc.types import Recommendation

from estimation.control.bias import bias_snapshot, build_bias_state
from estimation.control.config import profile_snapshot, profile_to_controller_config
from estimation.control.state_source import (
    StateUnavailableError,
    controller_state_from_cycle,
    history_for_greenhouse,
    latest_state_cycle_for_greenhouse,
    state_snapshot,
    validate_cycle_fresh,
)
from estimation.models import (
    AMPCRecommendation,
    Greenhouse,
    GreenhouseControlProfile,
    PipelineCycle,
)


class AMPCNotFound(Exception):
    """Requested greenhouse is missing or not owned by the user."""


class AMPCForbidden(Exception):
    """Requested greenhouse exists but cannot run AMPC."""


class ActuatorClient(Protocol):
    def send(self, command: ActuatorCommand) -> ActuatorResult:
        ...


@dataclass(frozen=True)
class _ActuatorDecision:
    enabled: bool
    executed: bool
    status: str
    command: ActuatorCommand | None = None
    http_status_code: int | None = None
    alert: str | None = None
    error: str | None = None


def run_ampc_for_greenhouse(
    *,
    user,
    greenhouse_id: int,
    now: datetime | None = None,
    beam_width: int = 32,
    actuator_client: ActuatorClient | None = None,
    command_id_factory: Callable[[], str] | None = None,
) -> AMPCRecommendation:
    """Run AMPC for one owned greenhouse and persist an audit row."""

    current_time = _aware(now or django_timezone.now())
    greenhouse = _owned_greenhouse(user=user, greenhouse_id=greenhouse_id)
    if not greenhouse.is_active:
        raise AMPCForbidden("greenhouse_inactive")

    profile, _ = GreenhouseControlProfile.objects.get_or_create(
        greenhouse=greenhouse,
    )

    try:
        config = profile_to_controller_config(profile)
    except ValueError as exc:
        return _persist_fail_closed(
            greenhouse=greenhouse,
            profile=profile,
            config=ControllerConfig(),
            safety_status=AMPCRecommendation.SafetyStatus.CONFIG_ERROR,
            reason=str(exc),
            now=current_time,
        )

    latest_cycle = latest_state_cycle_for_greenhouse(greenhouse.pk)
    if latest_cycle is None:
        return _persist_fail_closed(
            greenhouse=greenhouse,
            profile=profile,
            config=config,
            safety_status=AMPCRecommendation.SafetyStatus.PUMP_OFF_FAILSAFE,
            reason="state_unavailable",
            now=current_time,
        )

    try:
        validate_cycle_fresh(latest_cycle, config=config, now=current_time)
    except StateUnavailableError as exc:
        return _persist_fail_closed(
            greenhouse=greenhouse,
            profile=profile,
            config=config,
            safety_status=AMPCRecommendation.SafetyStatus.STALE_SAMPLE,
            reason=exc.code,
            now=current_time,
            state_cycle=latest_cycle,
        )

    try:
        plant_model = ARXPlantModel.load_artifact(
            settings.ARX_MODEL_PATH,
            pump_limits=config.pump,
        )
    except Exception as exc:  # noqa: BLE001
        return _persist_fail_closed(
            greenhouse=greenhouse,
            profile=profile,
            config=config,
            safety_status=AMPCRecommendation.SafetyStatus.MODEL_ERROR,
            reason=f"model_load_error:{exc.__class__.__name__}",
            now=current_time,
            state_cycle=latest_cycle,
        )

    history = history_for_greenhouse(
        greenhouse.pk,
        limit=plant_model.min_history_len,
    )
    if len(history) < plant_model.min_history_len:
        return _persist_fail_closed(
            greenhouse=greenhouse,
            profile=profile,
            config=config,
            safety_status=AMPCRecommendation.SafetyStatus.MODEL_ERROR,
            reason="history_too_short",
            now=current_time,
            state_cycle=latest_cycle,
        )

    used_today = used_today_pump_seconds(greenhouse=greenhouse, now=current_time)
    last_pump = last_recommendation_pump_seconds(greenhouse=greenhouse)
    controller_state = controller_state_from_cycle(
        latest_cycle,
        last_pump_seconds=last_pump,
    )
    bias_state = build_bias_state(
        greenhouse_id=greenhouse.pk,
        adaptive_config=config.adaptive,
    )
    adaptive_model = BiasCorrectedPlantModel(
        plant_model,
        bias=bias_state.current_bias,
        state_min=config.safety.state_min,
        state_max=config.safety.state_max,
    )
    try:
        recommendation = GridShootingSolver(
            config,
            beam_width=beam_width,
        ).recommend(
            state=controller_state,
            history=history,
            plant_model=adaptive_model,
            now=current_time,
            used_today_pump_seconds=used_today,
        )
    except Exception as exc:  # noqa: BLE001
        recommendation = _fail_closed_recommendation(
            config=config,
            safety_status=AMPCRecommendation.SafetyStatus.SOLVER_ERROR,
            reason=f"solver_error:{exc.__class__.__name__}",
        )

    actuator = _actuator_decision(
        state_cycle=latest_cycle,
        recommendation=recommendation,
        config=config,
        now=current_time,
        actuator_client=actuator_client,
        command_id_factory=command_id_factory,
    )
    final = _final_recommendation_after_actuator(
        recommendation,
        actuator=actuator,
        config=config,
    )
    return _persist_recommendation(
        greenhouse=greenhouse,
        profile=profile,
        config=config,
        recommendation=final,
        now=current_time,
        state_cycle=latest_cycle,
        bias_correction=bias_state.current_bias,
        bias_window_count=len(bias_state.residuals),
        used_today_pump_seconds=used_today,
        state_snapshot_json={
            **state_snapshot(latest_cycle),
            "bias": bias_snapshot(bias_state),
        },
        actuator=actuator,
    )


def get_owned_profile(
    *,
    user,
    greenhouse_id: int,
) -> GreenhouseControlProfile:
    greenhouse = _owned_greenhouse(user=user, greenhouse_id=greenhouse_id)
    return GreenhouseControlProfile.objects.get_or_create(greenhouse=greenhouse)[0]


def latest_recommendation_for_user(
    *,
    user,
    greenhouse_id: int,
) -> AMPCRecommendation | None:
    greenhouse = _owned_greenhouse(user=user, greenhouse_id=greenhouse_id)
    return (
        AMPCRecommendation.objects.filter(greenhouse=greenhouse)
        .order_by("-created_at", "-pk")
        .first()
    )


def used_today_pump_seconds(
    *,
    greenhouse: Greenhouse,
    now: datetime | None = None,
) -> float:
    current_time = _aware(now or django_timezone.now())
    local_now = django_timezone.localtime(current_time)
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    value = (
        AMPCRecommendation.objects.filter(
            greenhouse=greenhouse,
            created_at__gte=start,
            created_at__lt=end,
        ).aggregate(total=Sum("pump_seconds"))["total"]
        or 0.0
    )
    return float(value)


def last_recommendation_pump_seconds(*, greenhouse: Greenhouse) -> float:
    rec = (
        AMPCRecommendation.objects.filter(greenhouse=greenhouse)
        .order_by("-created_at", "-pk")
        .only("pump_seconds")
        .first()
    )
    if rec is None:
        return 0.0
    return float(rec.pump_seconds)


def _owned_greenhouse(*, user, greenhouse_id: int) -> Greenhouse:
    if not getattr(user, "is_authenticated", False):
        raise AMPCNotFound("greenhouse_not_found")
    try:
        return Greenhouse.objects.get(pk=greenhouse_id, owner=user)
    except Greenhouse.DoesNotExist as exc:
        raise AMPCNotFound("greenhouse_not_found") from exc


def _persist_fail_closed(
    *,
    greenhouse: Greenhouse,
    profile: GreenhouseControlProfile,
    config: ControllerConfig,
    safety_status: str,
    reason: str,
    now: datetime,
    state_cycle: PipelineCycle | None = None,
) -> AMPCRecommendation:
    recommendation = _fail_closed_recommendation(
        config=config,
        safety_status=safety_status,
        reason=reason,
    )
    return _persist_recommendation(
        greenhouse=greenhouse,
        profile=profile,
        config=config,
        recommendation=recommendation,
        now=now,
        state_cycle=state_cycle,
        bias_correction=0.0,
        bias_window_count=0,
        used_today_pump_seconds=used_today_pump_seconds(
            greenhouse=greenhouse,
            now=now,
        ),
        state_snapshot_json=state_snapshot(state_cycle),
        actuator=_ActuatorDecision(
            enabled=profile.actuator_enabled,
            executed=False,
            status="not_called",
            alert=_reason(reason),
        ),
    )


def _persist_recommendation(
    *,
    greenhouse: Greenhouse,
    profile: GreenhouseControlProfile,
    config: ControllerConfig,
    recommendation: Recommendation,
    now: datetime,
    state_cycle: PipelineCycle | None,
    bias_correction: float,
    bias_window_count: int,
    used_today_pump_seconds: float,
    state_snapshot_json: dict[str, object],
    actuator: _ActuatorDecision,
) -> AMPCRecommendation:
    command_json = actuator.command.to_dict() if actuator.command is not None else None
    with transaction.atomic():
        return AMPCRecommendation.objects.create(
            greenhouse=greenhouse,
            run_id=state_cycle.run_id if state_cycle is not None else None,
            state_cycle=state_cycle,
            mode=AMPCRecommendation.Mode.AMPC,
            pump_seconds=float(recommendation.pump_seconds),
            step_seconds=int(recommendation.step_seconds),
            predicted_soil_moisture_json=list(recommendation.predicted_soil_moisture),
            target_low=float(recommendation.target_band["low"]),
            target_high=float(recommendation.target_band["high"]),
            cost=float(max(recommendation.cost, 0.0)),
            safety_status=recommendation.safety_status,
            reason=_reason(recommendation.reason),
            bias_correction=float(bias_correction),
            bias_window_count=int(bias_window_count),
            used_today_pump_seconds=float(used_today_pump_seconds),
            config_snapshot_json=profile_snapshot(profile),
            state_snapshot_json=state_snapshot_json,
            actuator_enabled=bool(actuator.enabled),
            actuator_executed=bool(actuator.executed),
            actuator_status=actuator.status,
            actuator_command_json=command_json,
            actuator_http_status_code=actuator.http_status_code,
            actuator_alert=_optional_reason(actuator.alert),
            actuator_error=_optional_reason(actuator.error),
        )


def _actuator_decision(
    *,
    state_cycle: PipelineCycle,
    recommendation: Recommendation,
    config: ControllerConfig,
    now: datetime,
    actuator_client: ActuatorClient | None,
    command_id_factory: Callable[[], str] | None,
) -> _ActuatorDecision:
    if not config.actuator.enabled:
        return _ActuatorDecision(enabled=False, executed=False, status="disabled")

    if recommendation.safety_status != AMPCRecommendation.SafetyStatus.SAFE:
        return _ActuatorDecision(
            enabled=True,
            executed=False,
            status="not_called",
            alert=_reason(recommendation.reason),
        )

    try:
        configured_client = HTTPActuatorClient.from_config(config.actuator)
        client = actuator_client if actuator_client is not None else configured_client
    except ValueError as exc:
        return _ActuatorDecision(
            enabled=True,
            executed=False,
            status="config_error",
            alert=str(exc),
            error=str(exc),
        )

    try:
        command = _command_for_recommendation(
            state_cycle=state_cycle,
            recommendation=recommendation,
            config=config,
            now=now,
            command_id_factory=command_id_factory,
        )
    except ValueError as exc:
        return _ActuatorDecision(
            enabled=True,
            executed=False,
            status="config_error",
            alert=str(exc),
            error=str(exc),
        )

    try:
        result = client.send(command)
    except Exception as exc:  # noqa: BLE001
        fail_command = _fail_closed_command(
            state_cycle=state_cycle,
            config=config,
            now=now,
            reason=f"actuator_send_error:{exc.__class__.__name__}",
            command_id_factory=command_id_factory,
        )
        return _ActuatorDecision(
            enabled=True,
            executed=False,
            status="http_error",
            command=fail_command,
            alert="actuator_http_failure",
            error=exc.__class__.__name__,
        )
    if result.executed:
        return _ActuatorDecision(
            enabled=True,
            executed=True,
            status=result.status,
            command=result.command,
            http_status_code=result.http_status_code,
            alert=result.alert,
            error=result.error,
        )

    fail_command = _fail_closed_command(
        state_cycle=state_cycle,
        config=config,
        now=now,
        reason=result.alert or result.status,
        command_id_factory=command_id_factory,
    )
    return _ActuatorDecision(
        enabled=True,
        executed=False,
        status=result.status,
        command=fail_command,
        http_status_code=result.http_status_code,
        alert=result.alert,
        error=result.error,
    )


def _final_recommendation_after_actuator(
    recommendation: Recommendation,
    *,
    actuator: _ActuatorDecision,
    config: ControllerConfig,
) -> Recommendation:
    if recommendation.safety_status != AMPCRecommendation.SafetyStatus.SAFE:
        return Recommendation(
            pump_seconds=config.safety.fail_closed_pump_seconds,
            step_seconds=recommendation.step_seconds,
            predicted_soil_moisture=recommendation.predicted_soil_moisture,
            target_band=recommendation.target_band,
            cost=recommendation.cost,
            safety_status=recommendation.safety_status,
            reason=_reason(recommendation.reason),
        )
    if not actuator.enabled or actuator.executed:
        return recommendation
    if actuator.status == "disabled":
        return recommendation

    status = (
        AMPCRecommendation.SafetyStatus.CONFIG_ERROR
        if actuator.status == "config_error"
        else AMPCRecommendation.SafetyStatus.ACTUATOR_ERROR
    )
    return Recommendation(
        pump_seconds=config.safety.fail_closed_pump_seconds,
        step_seconds=recommendation.step_seconds,
        predicted_soil_moisture=recommendation.predicted_soil_moisture,
        target_band=recommendation.target_band,
        cost=recommendation.cost,
        safety_status=status,
        reason=_reason(actuator.alert or actuator.error or actuator.status),
    )


def _command_for_recommendation(
    *,
    state_cycle: PipelineCycle,
    recommendation: Recommendation,
    config: ControllerConfig,
    now: datetime,
    command_id_factory: Callable[[], str] | None,
) -> ActuatorCommand:
    is_safe = recommendation.safety_status == AMPCRecommendation.SafetyStatus.SAFE
    pump_seconds = (
        recommendation.pump_seconds
        if is_safe
        else config.safety.fail_closed_pump_seconds
    )
    reason = "ampc_recommendation_safe" if is_safe else recommendation.reason
    return ActuatorCommand(
        command_id=_command_id(command_id_factory),
        timestamp=now,
        run_id=state_cycle.run_id,
        pump_seconds=config.pump.clamp(pump_seconds),
        step_seconds=config.step_seconds,
        mode="auto",
        reason=_reason(reason),
        safety_status=recommendation.safety_status,
    )


def _fail_closed_command(
    *,
    state_cycle: PipelineCycle,
    config: ControllerConfig,
    now: datetime,
    reason: str,
    command_id_factory: Callable[[], str] | None,
) -> ActuatorCommand:
    return ActuatorCommand(
        command_id=_command_id(command_id_factory),
        timestamp=now,
        run_id=state_cycle.run_id,
        pump_seconds=config.safety.fail_closed_pump_seconds,
        step_seconds=config.step_seconds,
        mode="auto",
        reason=_reason(reason),
        safety_status=AMPCRecommendation.SafetyStatus.ACTUATOR_ERROR,
    )


def _fail_closed_recommendation(
    *,
    config: ControllerConfig,
    safety_status: str,
    reason: str,
) -> Recommendation:
    return Recommendation(
        pump_seconds=config.safety.fail_closed_pump_seconds,
        step_seconds=config.step_seconds,
        predicted_soil_moisture=(),
        target_band={
            "low": config.target_band.low,
            "high": config.target_band.high,
        },
        cost=0.0,
        safety_status=safety_status,
        reason=_reason(reason),
    )


def _command_id(factory: Callable[[], str] | None) -> str:
    if factory is None:
        return str(uuid4())
    value = factory()
    if not value:
        raise ValueError("command_id must not be empty")
    return value


def _reason(value: str) -> str:
    clean = (value or "unknown").strip()
    return clean[:255] or "unknown"


def _optional_reason(value: str | None) -> str | None:
    if value is None:
        return None
    return _reason(value)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
