"""State and history contracts shared by the plant adapter and solver."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any, Mapping


def _finite_or_none(value: float | int | None, field_name: str) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return numeric


def _required_finite(value: float | int | None, field_name: str) -> float:
    numeric = _finite_or_none(value, field_name)
    if numeric is None:
        raise ValueError(f"{field_name} is required")
    return numeric


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an int or null")
    return value


@dataclass(frozen=True)
class PlantRecord:
    """One ARX-compatible row at a control step."""

    soil_moisture: float
    temperature: float
    humidity: float
    light: float
    drip: float = 0.0
    mist: float = 0.0
    fan: float = 0.0

    def __post_init__(self) -> None:
        for field_name, value in (
            ("soil_moisture", self.soil_moisture),
            ("temperature", self.temperature),
            ("humidity", self.humidity),
            ("light", self.light),
            ("drip", self.drip),
            ("mist", self.mist),
            ("fan", self.fan),
        ):
            _required_finite(value, field_name)


@dataclass(frozen=True)
class ControllerState:
    """Latest controller state from Kalman/live payload."""

    timestamp: datetime
    kf_x_posterior: float | None = None
    raw_soil_moisture: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    light: float | None = None
    last_pump_seconds: float = 0.0
    run_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        _finite_or_none(self.kf_x_posterior, "kf_x_posterior")
        _finite_or_none(self.raw_soil_moisture, "raw_soil_moisture")
        _finite_or_none(self.temperature, "temperature")
        _finite_or_none(self.humidity, "humidity")
        _finite_or_none(self.light, "light")
        _required_finite(self.last_pump_seconds, "last_pump_seconds")
        _optional_int(self.run_id, "run_id")

    @property
    def soil_moisture(self) -> float:
        """Prefer Kalman posterior, then fallback to raw soil moisture."""
        posterior = _finite_or_none(self.kf_x_posterior, "kf_x_posterior")
        if posterior is not None:
            return posterior
        raw = _finite_or_none(self.raw_soil_moisture, "raw_soil_moisture")
        if raw is not None:
            return raw
        raise ValueError("state requires kf_x_posterior or raw_soil_moisture")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ControllerState":
        raw_ts = payload.get("timestamp")
        if isinstance(raw_ts, datetime):
            timestamp = raw_ts
        elif isinstance(raw_ts, str):
            timestamp = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        else:
            raise ValueError("timestamp must be an ISO string or datetime")

        return cls(
            timestamp=timestamp,
            kf_x_posterior=_finite_or_none(
                payload.get("kf_x_posterior"),
                "kf_x_posterior",
            ),
            raw_soil_moisture=_finite_or_none(
                payload.get("raw_soil_moisture"),
                "raw_soil_moisture",
            ),
            temperature=_finite_or_none(payload.get("temperature"), "temperature"),
            humidity=_finite_or_none(payload.get("humidity"), "humidity"),
            light=_finite_or_none(payload.get("light"), "light"),
            last_pump_seconds=_required_finite(
                payload.get("last_pump_seconds", 0.0),
                "last_pump_seconds",
            ),
            run_id=_optional_int(payload.get("run_id"), "run_id"),
        )

    def to_plant_record(self, *, drip: float = 0.0) -> PlantRecord:
        return PlantRecord(
            soil_moisture=self.soil_moisture,
            temperature=_required_finite(self.temperature, "temperature"),
            humidity=_required_finite(self.humidity, "humidity"),
            light=_required_finite(self.light, "light"),
            drip=drip,
        )


@dataclass(frozen=True)
class DisturbanceForecast:
    """Measured-hold forecast for exogenous signals."""

    temperature: tuple[float, ...]
    humidity: tuple[float, ...]
    light: tuple[float, ...]

    def __post_init__(self) -> None:
        lengths = {len(self.temperature), len(self.humidity), len(self.light)}
        if len(lengths) != 1:
            raise ValueError("disturbance forecast channels must align")
        if next(iter(lengths)) == 0:
            raise ValueError("disturbance forecast must not be empty")
        for name, values in (
            ("temperature", self.temperature),
            ("humidity", self.humidity),
            ("light", self.light),
        ):
            for value in values:
                _required_finite(value, name)

    @property
    def horizon_steps(self) -> int:
        return len(self.temperature)

    @classmethod
    def measured_hold(
        cls,
        state: ControllerState,
        horizon_steps: int,
    ) -> "DisturbanceForecast":
        if horizon_steps < 1:
            raise ValueError("horizon_steps must be >= 1")
        temperature = _required_finite(state.temperature, "temperature")
        humidity = _required_finite(state.humidity, "humidity")
        light = _required_finite(state.light, "light")
        return cls(
            temperature=(temperature,) * horizon_steps,
            humidity=(humidity,) * horizon_steps,
            light=(light,) * horizon_steps,
        )

    def record_at(
        self,
        index: int,
        *,
        soil_moisture: float,
        drip: float,
    ) -> PlantRecord:
        if not (0 <= index < self.horizon_steps):
            raise IndexError("forecast index out of range")
        return PlantRecord(
            soil_moisture=soil_moisture,
            temperature=self.temperature[index],
            humidity=self.humidity[index],
            light=self.light[index],
            drip=drip,
        )
