"""Bias adaptation layer for v3 AMPC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Sequence

from mpc.config import AdaptiveConfig
from mpc.plant import PlantModel
from mpc.state import DisturbanceForecast, PlantRecord

_MAX_FUTURE_SKEW_SECONDS = 30.0
_OUTLIER_FACTOR = 2.0


@dataclass(frozen=True)
class BiasState:
    """Current additive soil-moisture bias and accepted residual window."""

    residuals: tuple[float, ...] = ()
    current_bias: float = 0.0
    last_updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.current_bias):
            raise ValueError("current_bias must be finite")
        for residual in self.residuals:
            if not isfinite(residual):
                raise ValueError("residuals must be finite")
        if self.last_updated_at is not None and not isinstance(
            self.last_updated_at,
            datetime,
        ):
            raise TypeError("last_updated_at must be a datetime or None")


@dataclass(frozen=True)
class BiasUpdate:
    state: BiasState
    accepted: bool
    reason: str
    residual: float | None = None


class BiasEstimator:
    """Maintain a clipped moving-average bias from recent forecast residuals."""

    def __init__(
        self,
        config: AdaptiveConfig,
        *,
        stale_after_seconds: int,
    ) -> None:
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be > 0")
        self.config = config
        self.stale_after_seconds = stale_after_seconds

    def observe(
        self,
        state: BiasState,
        *,
        predicted: float | None,
        observed: float | None,
        observed_at: datetime,
        now: datetime | None = None,
    ) -> BiasUpdate:
        if not self.config.enabled:
            return BiasUpdate(state=state, accepted=False, reason="disabled")
        if not isinstance(observed_at, datetime):
            return BiasUpdate(
                state=state,
                accepted=False,
                reason="missing_timestamp",
            )
        if predicted is None or observed is None:
            return BiasUpdate(state=state, accepted=False, reason="missing_residual")
        if not isfinite(predicted) or not isfinite(observed):
            return BiasUpdate(state=state, accepted=False, reason="missing_residual")

        current_time = _aware(now or observed_at)
        sample_time = _aware(observed_at)
        age_seconds = (current_time - sample_time).total_seconds()
        if age_seconds > self.stale_after_seconds:
            return BiasUpdate(state=state, accepted=False, reason="stale_residual")
        if age_seconds < -_MAX_FUTURE_SKEW_SECONDS:
            return BiasUpdate(state=state, accepted=False, reason="stale_residual")

        residual = observed - predicted
        max_outlier = max(self.config.max_abs_bias * _OUTLIER_FACTOR, 1e-9)
        if abs(residual) > max_outlier:
            return BiasUpdate(
                state=state,
                accepted=False,
                reason="outlier_residual",
                residual=residual,
            )

        residuals = (state.residuals + (residual,))[-self.config.bias_window :]
        bias = _clip(
            sum(residuals) / len(residuals),
            -self.config.max_abs_bias,
            self.config.max_abs_bias,
        )
        return BiasUpdate(
            state=BiasState(
                residuals=residuals,
                current_bias=bias,
                last_updated_at=sample_time,
            ),
            accepted=True,
            reason="accepted",
            residual=residual,
        )


class BiasCorrectedPlantModel:
    """Plant model wrapper that adds a bounded bias to horizon predictions."""

    def __init__(
        self,
        base_model: PlantModel,
        *,
        bias: float,
        state_min: float = 0.0,
        state_max: float = 100.0,
    ) -> None:
        if not isfinite(bias):
            raise ValueError("bias must be finite")
        if not (isfinite(state_min) and isfinite(state_max)):
            raise ValueError("state bounds must be finite")
        if state_min >= state_max:
            raise ValueError("state_min must be < state_max")
        self.base_model = base_model
        self.bias = bias
        self.state_min = state_min
        self.state_max = state_max

    @property
    def min_history_len(self) -> int:
        return self.base_model.min_history_len

    def predict_next(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: float,
        step_seconds: int,
        disturbance: PlantRecord | None = None,
    ) -> float:
        prediction = self.base_model.predict_next(
            history,
            pump_seconds=pump_seconds,
            step_seconds=step_seconds,
            disturbance=disturbance,
        )
        if not isfinite(prediction):
            raise ValueError("base prediction must be finite")
        return _clip(prediction + self.bias, self.state_min, self.state_max)

    def forecast(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: Sequence[float],
        step_seconds: int,
        disturbances: DisturbanceForecast,
    ) -> tuple[float, ...]:
        if len(pump_seconds) != disturbances.horizon_steps:
            raise ValueError("pump sequence and disturbance horizon must align")
        working_history = list(history)
        if len(working_history) < self.min_history_len:
            raise ValueError(
                "history too short for bias-corrected forecast: "
                f"{len(working_history)} < {self.min_history_len}"
            )

        predictions: list[float] = []
        current_soil = working_history[-1].soil_moisture
        for index, pump in enumerate(pump_seconds):
            disturbance = disturbances.record_at(
                index,
                soil_moisture=current_soil,
                drip=_pump_duty(pump, step_seconds),
            )
            current_soil = self.predict_next(
                working_history,
                pump_seconds=pump,
                step_seconds=step_seconds,
                disturbance=disturbance,
            )
            predictions.append(current_soil)
            working_history.append(
                PlantRecord(
                    soil_moisture=current_soil,
                    temperature=disturbance.temperature,
                    humidity=disturbance.humidity,
                    light=disturbance.light,
                    drip=disturbance.drip,
                    mist=disturbance.mist,
                    fan=disturbance.fan,
                )
            )
        return tuple(predictions)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _clip(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def _pump_duty(pump_seconds: float, step_seconds: int) -> float:
    if step_seconds <= 0:
        raise ValueError("step_seconds must be > 0")
    if not isfinite(pump_seconds):
        raise ValueError("pump_seconds must be finite")
    return pump_seconds / float(step_seconds)
