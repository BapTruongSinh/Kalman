"""Read AMPC state and ARX-compatible history from persisted Kalman cycles."""

from __future__ import annotations

from datetime import datetime, timezone

from django.db.models import QuerySet
from django.utils import timezone as django_timezone
from mpc.config import ControllerConfig
from mpc.state import ControllerState, PlantRecord

from estimation.models import PipelineCycle

_MAX_FUTURE_SKEW_SECONDS = 30.0


class StateUnavailableError(ValueError):
    """Raised when DB state cannot safely seed AMPC."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def latest_state_cycle_for_greenhouse(greenhouse_id: int) -> PipelineCycle | None:
    """Return newest valid Kalman state cycle for one greenhouse."""

    return _valid_state_cycles(greenhouse_id).order_by("-sample_ts", "-cycle_index").first()


def history_for_greenhouse(
    greenhouse_id: int,
    *,
    limit: int,
) -> tuple[PlantRecord, ...]:
    """Return causal ARX history ordered oldest -> newest for one greenhouse."""

    if limit < 1:
        raise ValueError("history limit must be >= 1")
    rows = list(
        _valid_state_cycles(greenhouse_id)
        .order_by("-sample_ts", "-cycle_index")
        .only(
            "kf_x_posterior",
            "raw_temperature",
            "raw_humidity",
            "raw_light",
            "raw_drip",
            "raw_mist",
            "raw_fan",
        )[:limit]
    )
    return tuple(_cycle_to_plant_record(row) for row in reversed(rows))


def controller_state_from_cycle(
    cycle: PipelineCycle,
    *,
    last_pump_seconds: float,
) -> ControllerState:
    """Build the public MPC ControllerState from a PipelineCycle."""

    return ControllerState(
        timestamp=cycle.sample_ts,
        kf_x_posterior=cycle.kf_x_posterior,
        raw_soil_moisture=cycle.raw_soil_moisture,
        temperature=cycle.raw_temperature,
        humidity=cycle.raw_humidity,
        light=cycle.raw_light,
        last_pump_seconds=last_pump_seconds,
        run_id=cycle.run_id,
    )


def validate_cycle_fresh(
    cycle: PipelineCycle,
    *,
    config: ControllerConfig,
    now: datetime | None = None,
) -> None:
    """Reject stale or far-future state before model/solver execution."""

    current_time = _aware(now or django_timezone.now())
    sample_time = _aware(cycle.sample_ts)
    age_seconds = (current_time - sample_time).total_seconds()
    if age_seconds > config.safety.stale_after_seconds:
        raise StateUnavailableError("stale_sample")
    if age_seconds < -_MAX_FUTURE_SKEW_SECONDS:
        raise StateUnavailableError("future_sample")


def state_snapshot(cycle: PipelineCycle | None) -> dict[str, object]:
    """Return a JSON-safe state-source snapshot for audit storage."""

    if cycle is None:
        return {"state_cycle_id": None, "state_available": False}
    return {
        "state_available": True,
        "state_cycle_id": cycle.pk,
        "greenhouse_id": cycle.greenhouse_id,
        "run_id": cycle.run_id,
        "sample_ts": cycle.sample_ts.isoformat(),
        "kf_x_posterior": cycle.kf_x_posterior,
        "raw_soil_moisture": cycle.raw_soil_moisture,
        "temperature": cycle.raw_temperature,
        "humidity": cycle.raw_humidity,
        "light": cycle.raw_light,
        "arx_predicted": cycle.arx_predicted,
    }


def _valid_state_cycles(greenhouse_id: int) -> QuerySet[PipelineCycle]:
    return PipelineCycle.objects.filter(
        greenhouse_id=greenhouse_id,
        cycle_status=PipelineCycle.CycleStatus.OK,
        preprocess_status=PipelineCycle.PreprocessStatus.VALID,
        kf_x_posterior__isnull=False,
        raw_temperature__isnull=False,
        raw_humidity__isnull=False,
        raw_light__isnull=False,
    )


def _cycle_to_plant_record(cycle: PipelineCycle) -> PlantRecord:
    return PlantRecord(
        soil_moisture=float(cycle.kf_x_posterior),
        temperature=float(cycle.raw_temperature),
        humidity=float(cycle.raw_humidity),
        light=float(cycle.raw_light),
        drip=float(cycle.raw_drip or 0.0),
        mist=float(cycle.raw_mist or 0.0),
        fan=float(cycle.raw_fan or 0.0),
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
