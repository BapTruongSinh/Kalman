"""Deterministic grid-shooting MPC recommendation solver."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Sequence

from mpc.config import ControllerConfig
from mpc.plant import PlantModel
from mpc.solver.cost import TrajectoryCost, score_trajectory
from mpc.state import ControllerState, DisturbanceForecast, PlantRecord
from mpc.types import Recommendation, SafetyStatus


@dataclass(frozen=True)
class CandidateResult:
    first_pump_seconds: float
    pump_sequence: tuple[float, ...]
    predictions: tuple[float, ...]
    cost: TrajectoryCost


class GridShootingSolver:
    """Evaluate deterministic pump sequences on the configured pump grid."""

    _MAX_FUTURE_SKEW_SECONDS = 30.0

    def __init__(
        self,
        config: ControllerConfig | None = None,
        *,
        beam_width: int = 32,
    ) -> None:
        if beam_width < 1:
            raise ValueError("beam_width must be >= 1")
        self.config = config or ControllerConfig()
        self.beam_width = beam_width

    def recommend(
        self,
        *,
        state: ControllerState,
        history: Sequence[PlantRecord],
        plant_model: PlantModel,
        now: datetime | None = None,
        used_today_pump_seconds: float = 0.0,
    ) -> Recommendation:
        try:
            self._validate_state(state, now=now)
            disturbances = DisturbanceForecast.measured_hold(
                state,
                self.config.horizon_steps,
            )
        except ValueError as exc:
            reason = str(exc)
            if "stale" in reason:
                return self._fail_closed("stale_sample", "stale_sample")
            return self._fail_closed("pump_off_failsafe", reason)

        if not isfinite(used_today_pump_seconds) or used_today_pump_seconds < 0.0:
            return self._fail_closed("config_error", "used_today_invalid")
        if len(history) < plant_model.min_history_len:
            return self._fail_closed("model_error", "history_too_short")

        try:
            forecast_history = _history_with_state_latest(history, state)
        except ValueError as exc:
            return self._fail_closed("pump_off_failsafe", str(exc))

        try:
            best = self._solve(
                state=state,
                history=forecast_history,
                plant_model=plant_model,
                disturbances=disturbances,
                used_today_pump_seconds=used_today_pump_seconds,
            )
        except RuntimeError as exc:
            return self._fail_closed("solver_error", str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._fail_closed("model_error", str(exc))
        return Recommendation(
            pump_seconds=self.config.pump.clamp(best.first_pump_seconds),
            step_seconds=self.config.step_seconds,
            predicted_soil_moisture=best.predictions,
            target_band={
                "low": self.config.target_band.low,
                "high": self.config.target_band.high,
            },
            cost=best.cost.total,
            safety_status="safe",
            reason=self._reason_for(state.soil_moisture),
        )

    def _solve(
        self,
        *,
        state: ControllerState,
        history: Sequence[PlantRecord],
        plant_model: PlantModel,
        disturbances: DisturbanceForecast,
        used_today_pump_seconds: float,
    ) -> CandidateResult:
        candidates = self.config.pump.candidates()
        if not candidates:
            raise RuntimeError("no pump candidates")

        beam: list[tuple[float, ...]] = [()]
        evaluated: list[CandidateResult] = []
        for step in range(1, self.config.horizon_steps + 1):
            evaluated = [
                self._evaluate_sequence(
                    sequence=sequence + (candidate,),
                    state=state,
                    history=history,
                    plant_model=plant_model,
                    disturbances=_slice_disturbances(disturbances, step),
                    used_today_pump_seconds=used_today_pump_seconds,
                )
                for sequence in beam
                for candidate in candidates
            ]
            evaluated.sort(
                key=lambda result: (
                    result.cost.total,
                    result.first_pump_seconds,
                    result.pump_sequence,
                )
            )
            beam = [
                result.pump_sequence
                for result in evaluated[: self.beam_width]
            ]

        return min(
            evaluated,
            key=lambda result: (
                result.cost.total,
                result.first_pump_seconds,
                result.pump_sequence,
            ),
        )

    def _evaluate_sequence(
        self,
        *,
        sequence: tuple[float, ...],
        state: ControllerState,
        history: Sequence[PlantRecord],
        plant_model: PlantModel,
        disturbances: DisturbanceForecast,
        used_today_pump_seconds: float,
    ) -> CandidateResult:
        predictions = plant_model.forecast(
            history,
            pump_seconds=sequence,
            step_seconds=self.config.step_seconds,
            disturbances=disturbances,
        )
        cost = score_trajectory(
            predictions=predictions,
            pump_seconds=sequence,
            previous_pump_seconds=state.last_pump_seconds,
            used_today_pump_seconds=used_today_pump_seconds,
            config=self.config,
        )
        return CandidateResult(
            first_pump_seconds=sequence[0],
            pump_sequence=sequence,
            predictions=predictions,
            cost=cost,
        )

    def _validate_state(
        self,
        state: ControllerState,
        *,
        now: datetime | None,
    ) -> None:
        soil_moisture = state.soil_moisture
        if not (
            self.config.safety.state_min
            <= soil_moisture
            <= self.config.safety.state_max
        ):
            raise ValueError("state_out_of_bounds")

        current_time = now or datetime.now(timezone.utc)
        sample_time = state.timestamp
        if sample_time.tzinfo is None:
            sample_time = sample_time.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        age_seconds = (current_time - sample_time).total_seconds()
        if age_seconds < -self._MAX_FUTURE_SKEW_SECONDS:
            raise ValueError("future_sample")
        if age_seconds > self.config.safety.stale_after_seconds:
            raise ValueError("stale_sample")

    def _reason_for(self, soil_moisture: float) -> str:
        if soil_moisture < self.config.target_band.low:
            return "below_target_margin"
        if soil_moisture > self.config.target_band.high:
            return "above_target_margin"
        return "in_target_band"

    def _fail_closed(
        self,
        safety_status: SafetyStatus,
        reason: str,
    ) -> Recommendation:
        return Recommendation(
            pump_seconds=self.config.safety.fail_closed_pump_seconds,
            step_seconds=self.config.step_seconds,
            predicted_soil_moisture=(),
            target_band={
                "low": self.config.target_band.low,
                "high": self.config.target_band.high,
            },
            cost=0.0,
            safety_status=safety_status,
            reason=reason,
        )


def recommend(
    *,
    state: ControllerState,
    history: Sequence[PlantRecord],
    plant_model: PlantModel,
    config: ControllerConfig | None = None,
    now: datetime | None = None,
    used_today_pump_seconds: float = 0.0,
) -> Recommendation:
    return GridShootingSolver(config).recommend(
        state=state,
        history=history,
        plant_model=plant_model,
        now=now,
        used_today_pump_seconds=used_today_pump_seconds,
    )


def _slice_disturbances(
    disturbances: DisturbanceForecast,
    horizon_steps: int,
) -> DisturbanceForecast:
    return DisturbanceForecast(
        temperature=disturbances.temperature[:horizon_steps],
        humidity=disturbances.humidity[:horizon_steps],
        light=disturbances.light[:horizon_steps],
    )


def _history_with_state_latest(
    history: Sequence[PlantRecord],
    state: ControllerState,
) -> tuple[PlantRecord, ...]:
    state_record = state.to_plant_record(drip=history[-1].drip)
    return tuple(history[:-1]) + (state_record,)
