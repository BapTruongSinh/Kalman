from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from django.conf import settings

from kalman.filter import AdaptiveKalmanCycle, KalmanConfig, KalmanState
from kalman.ingestion import (
    ProcessedRecord,
    RawRecord,
    ValidationResult,
    preprocess_single,
    validate_live_record,
)
from kalman.prediction import ARXPredictionAdapter

from .models import Device, DeviceState, EstimationCycle, ExperimentRun, Greenhouse, SensorData


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _latest_device_flag(device_type: str, *, greenhouse: Greenhouse | None = None) -> float:
    queryset = DeviceState.objects.filter(device__device_type=device_type)
    if greenhouse is not None:
        queryset = queryset.filter(device__greenhouse=greenhouse)
    state = (
        queryset
        .order_by('-updated_at', '-id')
        .first()
    )
    return 1.0 if state and state.is_on else 0.0


def raw_record_from_reading(reading: SensorData, *, row_index: int, greenhouse: Greenhouse | None = None) -> RawRecord:
    payload = reading.payload or {}
    return RawRecord(
        timestamp=reading.recorded_at,
        soil_moisture=_float_or_none(reading.soil_moisture),
        temperature=_float_or_none(reading.temperature),
        humidity=_float_or_none(reading.humidity),
        light=_float_or_none(reading.light),
        drip=_float_or_none(payload.get('drip')) if 'drip' in payload else _latest_device_flag(Device.DeviceType.PUMP, greenhouse=greenhouse),
        fan=_float_or_none(payload.get('fan')) if 'fan' in payload else _latest_device_flag(Device.DeviceType.FAN, greenhouse=greenhouse),
        mist=_float_or_none(payload.get('mist')) if 'mist' in payload else _latest_device_flag(Device.DeviceType.MIST, greenhouse=greenhouse),
        row_index=row_index,
    )


@lru_cache(maxsize=4)
def _load_arx_adapter(path: str) -> ARXPredictionAdapter:
    return ARXPredictionAdapter.load_artifact(Path(path))


def _prediction_adapter() -> ARXPredictionAdapter | None:
    path = str(getattr(settings, 'ARX_MODEL_PATH', ''))
    if not path:
        return None
    try:
        return _load_arx_adapter(path)
    except Exception:
        return None


def _live_kalman_config(reading: SensorData) -> KalmanConfig:
    return KalmanConfig(
        x0=_float_or_none(reading.soil_moisture) or 0.0,
        Q=float(getattr(settings, 'KALMAN_LIVE_Q', 12.0)),
        R0=float(getattr(settings, 'KALMAN_LIVE_R0', 1.0)),
        R_min=float(getattr(settings, 'KALMAN_LIVE_R_MIN', 0.25)),
        R_max=float(getattr(settings, 'KALMAN_LIVE_R_MAX', 4.0)),
        alpha=float(getattr(settings, 'KALMAN_LIVE_ALPHA', 0.5)),
    )


def _processed_from_cycle(cycle: EstimationCycle) -> ProcessedRecord:
    raw = RawRecord(
        timestamp=cycle.sample_ts,
        soil_moisture=cycle.raw_soil_moisture,
        temperature=cycle.raw_temperature,
        humidity=cycle.raw_humidity,
        light=cycle.raw_light,
        drip=cycle.raw_drip,
        fan=cycle.raw_fan,
        mist=cycle.raw_mist,
        row_index=cycle.cycle_index,
    )
    validation = ValidationResult(
        is_valid=cycle.preprocess_status == EstimationCycle.PreprocessStatus.VALID,
        status=cycle.validation_status or 'valid',
        reason=cycle.validation_reason or '',
    )
    return preprocess_single(raw, validation)


def _recent_processed_history(limit: int, *, greenhouse: Greenhouse | None = None, run: ExperimentRun | None = None) -> list[ProcessedRecord]:
    queryset = EstimationCycle.objects
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    if run is not None:
        queryset = queryset.filter(run=run)
    cycles = (
        queryset
        .filter(preprocess_status=EstimationCycle.PreprocessStatus.VALID)
        .exclude(raw_soil_moisture__isnull=True)
        .exclude(raw_temperature__isnull=True)
        .exclude(raw_humidity__isnull=True)
        .exclude(raw_light__isnull=True)
        .order_by('-sample_ts', '-id')[:limit]
    )
    return [_processed_from_cycle(cycle) for cycle in reversed(list(cycles))]


def _restore_estimator_state(
    estimator: AdaptiveKalmanCycle,
    *,
    greenhouse: Greenhouse | None = None,
    run: ExperimentRun | None = None,
) -> int:
    queryset = EstimationCycle.objects
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    if run is not None:
        queryset = queryset.filter(run=run)
    latest = queryset.order_by('-cycle_index', '-id').first()
    if latest is None:
        return 0

    if (
        latest.kf_x_posterior is not None
        and latest.kf_P_posterior is not None
        and latest.kf_R is not None
    ):
        config = estimator.config
        estimator._state = KalmanState(  # noqa: SLF001
            x_post=float(latest.kf_x_posterior),
            P_post=float(latest.kf_P_posterior),
            R=max(config.R_min, min(config.R_max, float(latest.kf_R))),
            step=latest.cycle_index + 1,
        )
    return latest.cycle_index + 1


def ensure_estimation_for_reading(
    reading: SensorData,
    *,
    greenhouse: Greenhouse | None = None,
    run: ExperimentRun | None = None,
) -> EstimationCycle:
    greenhouse = greenhouse or reading.greenhouse
    run_key = run.id if run is not None else 'sensor'
    ingest_dedupe_key = f"live|{run_key}|{reading.recorded_at.astimezone().isoformat()}"
    existing_query = EstimationCycle.objects.filter(ingest_dedupe_key=ingest_dedupe_key)
    if run is not None:
        existing_query = existing_query.filter(run=run)
    existing = existing_query.first()
    if existing is not None:
        return existing

    adapter = _prediction_adapter()
    estimator = AdaptiveKalmanCycle(_live_kalman_config(reading), adapter=adapter)
    cycle_index = _restore_estimator_state(estimator, greenhouse=greenhouse, run=run)
    min_history = getattr(adapter, 'min_history_len', 0) if adapter is not None else 0
    estimator._history = _recent_processed_history(max(min_history, 12), greenhouse=greenhouse, run=run)  # noqa: SLF001

    raw = raw_record_from_reading(reading, row_index=cycle_index, greenhouse=greenhouse)
    validation = validate_live_record(raw)
    processed = preprocess_single(raw, validation)
    result = estimator.step(processed, cycle_index=cycle_index)

    return EstimationCycle.objects.create(
        sample_ts=result.timestamp,
        cycle_index=result.cycle_index,
        run=run,
        greenhouse=greenhouse,
        slice_type='online',
        source_type='live',
        validation_status=validation.status,
        validation_reason=validation.reason,
        preprocess_status=result.preprocess_status,
        cycle_status=result.cycle_status,
        adaptive_status=result.adaptive_status,
        raw_soil_moisture=result.raw_soil_moisture,
        raw_temperature=raw.temperature,
        raw_humidity=raw.humidity,
        raw_light=raw.light,
        raw_drip=raw.drip,
        raw_mist=raw.mist,
        raw_fan=raw.fan,
        arx_predicted=result.arx_predicted,
        kf_x_prior=result.x_prior,
        kf_P_prior=result.P_prior,
        kf_innovation=result.innovation,
        kf_R=result.R,
        kf_K=result.K,
        kf_x_posterior=result.x_posterior,
        kf_P_posterior=result.P_posterior,
        latency_ms=result.latency_ms,
        error_message=result.error_message or '',
        ingest_dedupe_key=ingest_dedupe_key,
    )


def latest_estimation(*, greenhouse: Greenhouse | None = None) -> EstimationCycle | None:
    queryset = EstimationCycle.objects
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    return (
        queryset
        .exclude(kf_x_posterior__isnull=True)
        .order_by('-sample_ts', '-id')
        .first()
    )
