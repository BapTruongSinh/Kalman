from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404
from django.db.models import Sum
from django.utils import timezone

from mpc.adaptive import BiasCorrectedPlantModel, BiasState
from mpc.config import (
    AdaptiveConfig,
    ControllerConfig,
    CostWeights,
    PumpLimits,
    SafetyConfig,
    TargetBand,
)
from mpc.plant import ARXPlantModel
from mpc.solver import GridShootingSolver
from mpc.state import MAX_TRUSTED_KALMAN_R, ControllerState, PlantRecord
from mpc.types import Recommendation

from .estimation import ensure_estimation_for_reading, latest_estimation
from .models import (
    AMPCRecommendation,
    ControlProfile,
    ControlState,
    Device,
    DeviceCommand,
    EstimationCycle,
    ExperimentRun,
    Greenhouse,
    GreenhouseControlProfile,
    SensorData,
)
from .services import enqueue_device_command, notify_pending_commands


def get_control_profile() -> ControlProfile:
    profile, _ = ControlProfile.objects.get_or_create(singleton_key='main')
    return profile


def default_greenhouse(user=None) -> Greenhouse:
    queryset = Greenhouse.objects.filter(is_active=True)
    if user is not None and getattr(user, 'is_authenticated', False):
        queryset = queryset.filter(owner=user)
    greenhouse = queryset.order_by('id').first()
    if greenhouse is not None:
        return greenhouse

    owner = user if user is not None and getattr(user, 'is_authenticated', False) else get_user_model().objects.order_by('id').first()
    if owner is None:
        owner = get_user_model().objects.create_user(username='local_admin')
    return Greenhouse.objects.create(owner=owner, name='Main greenhouse', is_active=True)


def get_greenhouse_for_user(user, greenhouse_id: int) -> Greenhouse:
    queryset = Greenhouse.objects.filter(pk=greenhouse_id, is_active=True)
    if user is not None and getattr(user, 'is_authenticated', False):
        queryset = queryset.filter(owner=user)
    greenhouse = queryset.first()
    if greenhouse is None:
        raise Http404('greenhouse_not_found_or_forbidden')
    return greenhouse


def get_greenhouse_control_profile(greenhouse: Greenhouse) -> GreenhouseControlProfile:
    legacy = get_control_profile()
    profile, _ = GreenhouseControlProfile.objects.get_or_create(
        greenhouse=greenhouse,
        defaults={
            'crop_name': legacy.crop_name,
            'crop_kc': legacy.crop_kc,
            'target_low': legacy.target_low,
            'target_high': legacy.target_high,
            'step_seconds': legacy.step_seconds,
            'horizon_steps': legacy.horizon_steps,
            'pump_min_seconds': legacy.pump_min_seconds,
            'pump_max_seconds': legacy.pump_max_seconds,
            'pump_grid_seconds': legacy.pump_grid_seconds,
            'soft_daily_pump_cap_seconds': legacy.soft_daily_pump_cap_seconds,
            'cost_band_violation': legacy.weight_band,
            'cost_water_use': legacy.weight_water,
            'cost_switching': legacy.weight_switch,
            'cost_daily_cap_excess': legacy.weight_daily,
            'cost_terminal_band_violation': legacy.weight_terminal,
            'adaptive_enabled': legacy.adaptive_enabled,
            'adaptive_bias_window': legacy.adaptive_bias_window,
            'adaptive_max_abs_bias': legacy.adaptive_max_abs_bias,
            'safety_stale_after_seconds': legacy.stale_after_seconds,
            'actuator_enabled': legacy.actuator_enabled,
        },
    )
    return profile


def _profile_value(profile, greenhouse_name: str, legacy_name: str):
    if hasattr(profile, greenhouse_name):
        return getattr(profile, greenhouse_name)
    return getattr(profile, legacy_name)


def profile_to_config(profile: ControlProfile | GreenhouseControlProfile) -> ControllerConfig:
    return ControllerConfig(
        step_seconds=profile.step_seconds,
        horizon_steps=profile.horizon_steps,
        target_band=TargetBand(low=profile.target_low, high=profile.target_high),
        pump=PumpLimits(
            min_seconds=profile.pump_min_seconds,
            max_seconds=profile.pump_max_seconds,
            grid_seconds=profile.pump_grid_seconds,
        ),
        cost=CostWeights(
            band_violation=_profile_value(profile, 'cost_band_violation', 'weight_band'),
            terminal_band_violation=_profile_value(profile, 'cost_terminal_band_violation', 'weight_terminal'),
            water_use=_profile_value(profile, 'cost_water_use', 'weight_water'),
            switching=_profile_value(profile, 'cost_switching', 'weight_switch'),
            daily_cap_excess=_profile_value(profile, 'cost_daily_cap_excess', 'weight_daily'),
        ),
        safety=SafetyConfig(
            stale_after_seconds=_profile_value(profile, 'safety_stale_after_seconds', 'stale_after_seconds'),
            soft_daily_pump_cap_seconds=profile.soft_daily_pump_cap_seconds,
        ),
        adaptive=AdaptiveConfig(
            enabled=profile.adaptive_enabled,
            bias_window=profile.adaptive_bias_window,
            max_abs_bias=profile.adaptive_max_abs_bias,
        ),
    )


def profile_snapshot(profile: ControlProfile | GreenhouseControlProfile) -> dict:
    return {
        'greenhouse_id': getattr(profile, 'greenhouse_id', None),
        'crop_name': profile.crop_name,
        'crop_kc': profile.crop_kc,
        'target_low': profile.target_low,
        'target_high': profile.target_high,
        'step_seconds': profile.step_seconds,
        'horizon_steps': profile.horizon_steps,
        'pump_min_seconds': profile.pump_min_seconds,
        'pump_max_seconds': profile.pump_max_seconds,
        'pump_grid_seconds': profile.pump_grid_seconds,
        'soft_daily_pump_cap_seconds': profile.soft_daily_pump_cap_seconds,
        'weights': {
            'band': _profile_value(profile, 'cost_band_violation', 'weight_band'),
            'water': _profile_value(profile, 'cost_water_use', 'weight_water'),
            'switch': _profile_value(profile, 'cost_switching', 'weight_switch'),
            'daily': _profile_value(profile, 'cost_daily_cap_excess', 'weight_daily'),
            'terminal': _profile_value(profile, 'cost_terminal_band_violation', 'weight_terminal'),
        },
        'adaptive_enabled': profile.adaptive_enabled,
        'adaptive_bias_window': profile.adaptive_bias_window,
        'adaptive_max_abs_bias': profile.adaptive_max_abs_bias,
        'stale_after_seconds': _profile_value(profile, 'safety_stale_after_seconds', 'stale_after_seconds'),
        'actuator_enabled': profile.actuator_enabled,
    }


def _latest_control_state(greenhouse: Greenhouse | None = None) -> ControlState:
    if greenhouse is None:
        control, _ = ControlState.objects.get_or_create(singleton_key='main')
        return control
    control, _ = ControlState.objects.get_or_create(
        greenhouse=greenhouse,
        defaults={'singleton_key': f'greenhouse:{greenhouse.id}'[:20]},
    )
    return control


def _latest_pump_seconds(greenhouse: Greenhouse | None = None) -> float:
    queryset = AMPCRecommendation.objects
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    latest = queryset.order_by('-created_at', '-id').first()
    return float(latest.pump_seconds) if latest else 0.0


def _used_today_pump_seconds(now: datetime, greenhouse: Greenhouse | None = None) -> float:
    day = timezone.localtime(now).date()
    queryset = AMPCRecommendation.objects.filter(created_at__date=day, safety_status='safe')
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    total = (
        queryset
        .aggregate(total=Sum('pump_seconds'))
        .get('total')
    )
    return float(total or 0.0)


def _raw_fallback_delta() -> float:
    return float(getattr(settings, 'AMPC_RAW_FALLBACK_DELTA', 8.0))


def _control_soil_moisture(cycle: EstimationCycle) -> float:
    raw = cycle.raw_soil_moisture
    posterior = cycle.kf_x_posterior
    kalman_r = cycle.kf_R
    if raw is not None and kalman_r is not None and float(kalman_r) > MAX_TRUSTED_KALMAN_R:
        return float(raw)
    if raw is not None and posterior is not None and abs(float(posterior) - float(raw)) > _raw_fallback_delta():
        return float(raw)
    if posterior is not None:
        return float(posterior)
    if raw is not None:
        return float(raw)
    raise ValueError('missing_soil_moisture')


def _uses_raw_fallback(cycle: EstimationCycle) -> bool:
    return (
        cycle.raw_soil_moisture is not None
        and (
            (
                cycle.kf_x_posterior is not None
                and abs(float(cycle.kf_x_posterior) - float(cycle.raw_soil_moisture)) > _raw_fallback_delta()
            )
            or (
                cycle.kf_R is not None
                and float(cycle.kf_R) > MAX_TRUSTED_KALMAN_R
            )
        )
    )


def _plant_record_from_cycle(cycle: EstimationCycle) -> PlantRecord:
    return PlantRecord(
        soil_moisture=_control_soil_moisture(cycle),
        temperature=float(cycle.raw_temperature),
        humidity=float(cycle.raw_humidity),
        light=float(cycle.raw_light),
        drip=float(cycle.raw_drip or 0.0),
        mist=float(cycle.raw_mist or 0.0),
        fan=float(cycle.raw_fan or 0.0),
    )


def _history(limit: int, greenhouse: Greenhouse | None = None) -> tuple[PlantRecord, ...]:
    queryset = EstimationCycle.objects
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    cycles = (
        queryset
        .exclude(kf_x_posterior__isnull=True)
        .exclude(raw_temperature__isnull=True)
        .exclude(raw_humidity__isnull=True)
        .exclude(raw_light__isnull=True)
        .order_by('-sample_ts', '-id')[:limit]
    )
    return tuple(_plant_record_from_cycle(cycle) for cycle in reversed(list(cycles)))


def _bias_state(profile: ControlProfile | GreenhouseControlProfile, now: datetime, greenhouse: Greenhouse | None = None) -> BiasState:
    if not profile.adaptive_enabled:
        return BiasState()
    queryset = EstimationCycle.objects
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    cycles = (
        queryset
        .exclude(arx_predicted__isnull=True)
        .exclude(kf_x_posterior__isnull=True)
        .order_by('-sample_ts', '-id')[:profile.adaptive_bias_window]
    )
    residuals = []
    for cycle in reversed(list(cycles)):
        residual = _control_soil_moisture(cycle) - float(cycle.arx_predicted)
        if abs(residual) <= profile.adaptive_max_abs_bias * 2.0:
            residuals.append(residual)
    residuals = residuals[-profile.adaptive_bias_window:]
    if not residuals:
        return BiasState(last_updated_at=now)
    bias = sum(residuals) / len(residuals)
    bias = max(-profile.adaptive_max_abs_bias, min(profile.adaptive_max_abs_bias, bias))
    return BiasState(tuple(residuals), current_bias=bias, last_updated_at=now)


def _state_snapshot(estimation: EstimationCycle, state: ControllerState) -> dict:
    return {
        'estimation_id': estimation.id,
        'run_id': estimation.run_id,
        'greenhouse_id': estimation.greenhouse_id,
        'timestamp': state.timestamp.isoformat(),
        'kf_x_posterior': estimation.kf_x_posterior,
        'kf_R': estimation.kf_R,
        'raw_soil_moisture': state.raw_soil_moisture,
        'control_soil_moisture': state.soil_moisture,
        'used_raw_fallback': _uses_raw_fallback(estimation),
        'temperature': state.temperature,
        'humidity': state.humidity,
        'light': state.light,
        'last_pump_seconds': state.last_pump_seconds,
    }


def _fail_recommendation(config: ControllerConfig, safety_status: str, reason: str) -> Recommendation:
    return Recommendation(
        pump_seconds=config.safety.fail_closed_pump_seconds,
        step_seconds=config.step_seconds,
        predicted_soil_moisture=(),
        target_band={'low': config.target_band.low, 'high': config.target_band.high},
        cost=0.0,
        safety_status=safety_status,
        reason=reason,
    )


def _persist_recommendation(
    *,
    profile: ControlProfile | GreenhouseControlProfile,
    config: ControllerConfig,
    recommendation: Recommendation,
    estimation: EstimationCycle | None,
    state: ControllerState | None,
    bias: BiasState,
    used_today: float,
    greenhouse: Greenhouse | None = None,
    run: ExperimentRun | None = None,
    sensor_data: SensorData | None = None,
    actuator_status: str = AMPCRecommendation.ActuatorStatus.NOT_CALLED,
) -> AMPCRecommendation:
    control = _latest_control_state(greenhouse)
    return AMPCRecommendation.objects.create(
        sensor_data=sensor_data,
        greenhouse=greenhouse,
        run=run,
        estimation=estimation,
        mode=control.mode,
        pump_seconds=float(recommendation.pump_seconds),
        step_seconds=int(recommendation.step_seconds),
        predicted_soil_moisture=list(recommendation.predicted_soil_moisture),
        target_band=dict(recommendation.target_band),
        objective_cost=float(recommendation.cost),
        safety_status=recommendation.safety_status,
        reason=recommendation.reason,
        bias_correction=float(bias.current_bias),
        bias_window_count=len(bias.residuals),
        used_today_pump_seconds=used_today,
        actuator_status=actuator_status,
        config_snapshot=profile_snapshot(profile),
        state_snapshot=_state_snapshot(estimation, state) if estimation and state else {},
    )


def _queue_pump_command(audit: AMPCRecommendation) -> AMPCRecommendation:
    if audit.safety_status != 'safe':
        audit.actuator_status = AMPCRecommendation.ActuatorStatus.UNSAFE_SKIPPED
        audit.save(update_fields=['actuator_status', 'updated_at'])
        return audit

    pumps = Device.objects.filter(device_type=Device.DeviceType.PUMP, is_enabled=True)
    if audit.greenhouse_id is not None:
        pumps = pumps.filter(greenhouse_id=audit.greenhouse_id)
    pump = pumps.first()
    if pump is None:
        audit.actuator_status = AMPCRecommendation.ActuatorStatus.DEVICE_NOT_FOUND
        audit.save(update_fields=['actuator_status', 'updated_at'])
        return audit

    command = enqueue_device_command(
        device=pump,
        command='pump_seconds',
        value=str(round(audit.pump_seconds, 3)),
        payload={
            'source': 'ampc',
            'recommendation_id': audit.id,
            'step_seconds': audit.step_seconds,
            'safety_status': audit.safety_status,
        },
    )
    audit.device_command = command
    audit.command_created = True
    audit.actuator_status = AMPCRecommendation.ActuatorStatus.QUEUED
    audit.save(update_fields=['device_command', 'command_created', 'actuator_status', 'updated_at'])
    notify_pending_commands()
    return audit


def run_auto_recommendation(
    *,
    create_command_if_auto: bool = True,
    user=None,
    greenhouse_id: int | None = None,
) -> AMPCRecommendation:
    greenhouse = get_greenhouse_for_user(user, greenhouse_id) if greenhouse_id is not None else default_greenhouse(user)
    profile = get_greenhouse_control_profile(greenhouse)
    config = profile_to_config(profile)
    now = timezone.now()
    used_today = _used_today_pump_seconds(now, greenhouse)
    bias = BiasState()

    latest = latest_estimation(greenhouse=greenhouse)
    if latest is None:
        reading = SensorData.objects.filter(greenhouse=greenhouse).order_by('-recorded_at', '-id').first()
        if reading is not None:
            latest = ensure_estimation_for_reading(reading, greenhouse=greenhouse)

    if latest is None:
        recommendation = _fail_recommendation(config, 'model_error', 'missing_estimation')
        return _persist_recommendation(
            profile=profile,
            config=config,
            recommendation=recommendation,
            estimation=None,
            state=None,
            bias=bias,
            used_today=used_today,
            greenhouse=greenhouse,
            sensor_data=None,
            actuator_status=(
                AMPCRecommendation.ActuatorStatus.UNSAFE_SKIPPED
                if profile.actuator_enabled
                else AMPCRecommendation.ActuatorStatus.DISABLED
            ),
        )

    sensor_data = SensorData.objects.filter(greenhouse=greenhouse, recorded_at=latest.sample_ts).order_by('-id').first()
    use_raw_fallback = _uses_raw_fallback(latest)
    state = ControllerState(
        timestamp=latest.sample_ts,
        kf_x_posterior=None if use_raw_fallback else latest.kf_x_posterior,
        kf_R=latest.kf_R,
        raw_soil_moisture=latest.raw_soil_moisture,
        temperature=latest.raw_temperature,
        humidity=latest.raw_humidity,
        light=latest.raw_light,
        last_pump_seconds=_latest_pump_seconds(greenhouse),
        run_id=latest.run_id,
    )

    try:
        plant = ARXPlantModel.load_artifact(
            Path(settings.ARX_MODEL_PATH),
            pump_limits=config.pump,
        )
        history = _history(max(plant.min_history_len, config.horizon_steps + plant.min_history_len), greenhouse)
        bias = _bias_state(profile, now, greenhouse)
        plant_model = (
            BiasCorrectedPlantModel(
                plant,
                bias=bias.current_bias,
                state_min=config.safety.state_min,
                state_max=config.safety.state_max,
            )
            if profile.adaptive_enabled
            else plant
        )
        recommendation = GridShootingSolver(config, beam_width=32).recommend(
            state=state,
            history=history,
            plant_model=plant_model,
            now=now,
            used_today_pump_seconds=used_today,
        )
    except Exception as exc:
        recommendation = _fail_recommendation(config, 'model_error', str(exc))

    audit = _persist_recommendation(
        profile=profile,
        config=config,
        recommendation=recommendation,
        estimation=latest,
        state=state,
        bias=bias,
        used_today=used_today,
        greenhouse=greenhouse,
        run=latest.run,
        sensor_data=sensor_data,
        actuator_status=AMPCRecommendation.ActuatorStatus.DISABLED if not profile.actuator_enabled else AMPCRecommendation.ActuatorStatus.NOT_CALLED,
    )

    control = _latest_control_state(greenhouse)
    if create_command_if_auto and profile.actuator_enabled and control.mode == ControlState.Mode.AUTO:
        return _queue_pump_command(audit)
    return audit


def latest_recommendation() -> AMPCRecommendation | None:
    return AMPCRecommendation.objects.order_by('-created_at', '-id').first()


def latest_recommendation_for_greenhouse(greenhouse: Greenhouse) -> AMPCRecommendation | None:
    return AMPCRecommendation.objects.filter(greenhouse=greenhouse).order_by('-created_at', '-id').first()
