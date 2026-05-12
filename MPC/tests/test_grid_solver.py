from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

import pytest

from mpc.config import ControllerConfig, CostWeights, PumpLimits, SafetyConfig
from mpc.solver import GridShootingSolver, score_trajectory
from mpc.state import ControllerState, DisturbanceForecast, PlantRecord

NOW = datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class LinearPlant:
    gain_per_full_pump: float = 1.0
    drift_per_step: float = 0.0
    min_history_len: int = 1

    def predict_next(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: float,
        step_seconds: int,
        disturbance: PlantRecord | None = None,
    ) -> float:
        return (
            history[-1].soil_moisture
            + self.drift_per_step
            + self.gain_per_full_pump * pump_seconds / float(step_seconds)
        )

    def forecast(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: Sequence[float],
        step_seconds: int,
        disturbances: DisturbanceForecast,
    ) -> tuple[float, ...]:
        current = history[-1].soil_moisture
        values: list[float] = []
        for pump in pump_seconds:
            current += (
                self.drift_per_step
                + self.gain_per_full_pump * pump / float(step_seconds)
            )
            values.append(current)
        return tuple(values)


@dataclass(frozen=True)
class BrokenPlant:
    min_history_len: int = 1

    def predict_next(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: float,
        step_seconds: int,
        disturbance: PlantRecord | None = None,
    ) -> float:
        raise ValueError("plant unavailable")

    def forecast(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: Sequence[float],
        step_seconds: int,
        disturbances: DisturbanceForecast,
    ) -> tuple[float, ...]:
        raise ValueError("plant unavailable")


def _state(
    soil: float | None,
    *,
    last_pump_seconds: float = 0.0,
    timestamp: datetime = NOW,
) -> ControllerState:
    return ControllerState(
        timestamp=timestamp,
        kf_x_posterior=soil,
        raw_soil_moisture=None,
        temperature=27.0,
        humidity=72.0,
        light=300.0,
        last_pump_seconds=last_pump_seconds,
    )


def _history(soil: float) -> list[PlantRecord]:
    return [
        PlantRecord(
            soil_moisture=soil,
            temperature=27.0,
            humidity=72.0,
            light=300.0,
        )
    ]


def test_grid_solver_in_band_prefers_no_pump() -> None:
    recommendation = GridShootingSolver().recommend(
        state=_state(60.0),
        history=_history(60.0),
        plant_model=LinearPlant(gain_per_full_pump=1.0),
        now=NOW,
    )

    assert recommendation.safety_status == "safe"
    assert recommendation.pump_seconds == 0.0
    assert recommendation.step_seconds == 300
    assert recommendation.reason == "field_capacity_or_wetter"
    assert set(recommendation.to_dict()) == {
        "pump_seconds",
        "step_seconds",
        "predicted_soil_moisture",
        "target_band",
        "cost",
        "safety_status",
        "reason",
        "fao56",
    }
    assert recommendation.fao56 is not None
    assert recommendation.fao56["initial_dr"] == pytest.approx(0.0)


def test_grid_solver_below_band_recommends_pump() -> None:
    recommendation = GridShootingSolver().recommend(
        state=_state(0.0),
        history=_history(0.0),
        plant_model=LinearPlant(gain_per_full_pump=2.0),
        now=NOW,
    )

    assert recommendation.safety_status == "safe"
    assert 0.0 < recommendation.pump_seconds <= 300.0
    assert recommendation.reason == "above_raw_stress"
    assert recommendation.fao56 is not None
    assert recommendation.fao56["initial_dr"] > recommendation.fao56["raw"]


def test_grid_solver_uses_state_as_latest_forecast_record() -> None:
    recommendation = GridShootingSolver().recommend(
        state=_state(0.0),
        history=_history(60.0),
        plant_model=LinearPlant(gain_per_full_pump=2.0),
        now=NOW,
    )

    assert recommendation.safety_status == "safe"
    assert recommendation.reason == "above_raw_stress"
    assert recommendation.pump_seconds > 0.0


def test_grid_solver_above_band_recommends_no_pump() -> None:
    recommendation = GridShootingSolver().recommend(
        state=_state(70.0),
        history=_history(70.0),
        plant_model=LinearPlant(gain_per_full_pump=2.0),
        now=NOW,
    )

    assert recommendation.safety_status == "safe"
    assert recommendation.pump_seconds == 0.0
    assert recommendation.reason == "field_capacity_or_wetter"


def test_grid_solver_respects_pump_bounds() -> None:
    config = ControllerConfig(pump=PumpLimits(max_seconds=60.0, grid_seconds=30.0))

    recommendation = GridShootingSolver(config).recommend(
        state=_state(40.0),
        history=_history(40.0),
        plant_model=LinearPlant(gain_per_full_pump=5.0),
        now=NOW,
    )

    assert 0.0 <= recommendation.pump_seconds <= 60.0


def test_grid_solver_switching_penalty_can_preserve_previous_command() -> None:
    config = ControllerConfig(
        cost=CostWeights(
            band_violation=0.0,
            terminal_band_violation=0.0,
            water_use=0.0,
            switching=1.0,
            daily_cap_excess=0.0,
        )
    )

    recommendation = GridShootingSolver(config).recommend(
        state=_state(60.0, last_pump_seconds=300.0),
        history=_history(60.0),
        plant_model=LinearPlant(gain_per_full_pump=0.0),
        now=NOW,
    )

    assert recommendation.pump_seconds == pytest.approx(300.0)


def test_score_trajectory_penalizes_soft_daily_cap_excess() -> None:
    cost = score_trajectory(
        predictions=(60.0,),
        pump_seconds=(300.0,),
        previous_pump_seconds=0.0,
        used_today_pump_seconds=1800.0,
        config=ControllerConfig(),
    )

    assert cost.daily_cap > 0.0
    assert cost.total >= cost.daily_cap


def test_score_trajectory_normalizes_water_and_switching_by_pump_max() -> None:
    config = ControllerConfig(
        pump=PumpLimits(max_seconds=20.0, grid_seconds=10.0),
        cost=CostWeights(
            band_violation=0.0,
            terminal_band_violation=0.0,
            water_use=2.0,
            switching=3.0,
            daily_cap_excess=0.0,
        ),
    )

    cost = score_trajectory(
        predictions=(60.0,),
        pump_seconds=(10.0,),
        previous_pump_seconds=0.0,
        used_today_pump_seconds=0.0,
        config=config,
    )

    assert cost.water == pytest.approx(2.0 * (10.0 / 20.0) ** 2)
    assert cost.switching == pytest.approx(3.0 * (10.0 / 20.0) ** 2)


def test_score_trajectory_daily_cap_uses_total_planned_excess_ratio() -> None:
    config = ControllerConfig(
        pump=PumpLimits(max_seconds=300.0, grid_seconds=300.0),
        cost=CostWeights(
            band_violation=0.0,
            terminal_band_violation=0.0,
            water_use=0.0,
            switching=0.0,
            daily_cap_excess=4.0,
        ),
        safety=SafetyConfig(soft_daily_pump_cap_seconds=100.0),
    )

    cost = score_trajectory(
        predictions=(60.0, 60.0),
        pump_seconds=(80.0, 50.0),
        previous_pump_seconds=0.0,
        used_today_pump_seconds=20.0,
        config=config,
    )

    expected_ratio = (20.0 + 130.0 - 100.0) / 100.0
    assert cost.daily_cap == pytest.approx(4.0 * expected_ratio**2)


def test_score_trajectory_terminal_cost_uses_final_band_error() -> None:
    config = ControllerConfig(
        cost=CostWeights(
            band_violation=0.0,
            terminal_band_violation=5.0,
            water_use=0.0,
            switching=0.0,
            daily_cap_excess=0.0,
        )
    )

    cost = score_trajectory(
        predictions=(60.0, 53.0),
        pump_seconds=(0.0, 0.0),
        previous_pump_seconds=0.0,
        used_today_pump_seconds=0.0,
        config=config,
    )

    assert cost.terminal == pytest.approx(5.0 * (55.0 - 53.0) ** 2)


def test_grid_solver_rejects_negative_used_today_fails_closed() -> None:
    recommendation = GridShootingSolver().recommend(
        state=_state(60.0),
        history=_history(60.0),
        plant_model=LinearPlant(),
        now=NOW,
        used_today_pump_seconds=-1.0,
    )

    assert recommendation.safety_status == "config_error"
    assert recommendation.pump_seconds == 0.0


def test_grid_solver_returns_same_output_for_same_input() -> None:
    solver = GridShootingSolver()
    kwargs = {
        "state": _state(50.0),
        "history": _history(50.0),
        "plant_model": LinearPlant(gain_per_full_pump=2.0),
        "now": NOW,
    }

    first = solver.recommend(**kwargs)
    second = solver.recommend(**kwargs)

    assert first == second


def test_grid_solver_stale_state_fails_closed() -> None:
    recommendation = GridShootingSolver().recommend(
        state=_state(60.0, timestamp=NOW - timedelta(seconds=601)),
        history=_history(60.0),
        plant_model=LinearPlant(),
        now=NOW,
    )

    assert recommendation.safety_status == "stale_sample"
    assert recommendation.pump_seconds == 0.0
    assert recommendation.predicted_soil_moisture == ()


def test_grid_solver_future_timestamp_fails_closed() -> None:
    recommendation = GridShootingSolver().recommend(
        state=_state(60.0, timestamp=NOW + timedelta(days=1)),
        history=_history(60.0),
        plant_model=LinearPlant(),
        now=NOW,
    )

    assert recommendation.safety_status == "pump_off_failsafe"
    assert recommendation.pump_seconds == 0.0


def test_grid_solver_missing_state_fails_closed() -> None:
    recommendation = GridShootingSolver().recommend(
        state=_state(None),
        history=_history(60.0),
        plant_model=LinearPlant(),
        now=NOW,
    )

    assert recommendation.safety_status == "pump_off_failsafe"
    assert recommendation.pump_seconds == 0.0


def test_grid_solver_model_error_fails_closed() -> None:
    recommendation = GridShootingSolver().recommend(
        state=_state(60.0),
        history=_history(60.0),
        plant_model=BrokenPlant(),
        now=NOW,
    )

    assert recommendation.safety_status == "model_error"
    assert recommendation.pump_seconds == 0.0
