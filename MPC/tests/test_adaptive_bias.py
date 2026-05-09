from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

import pytest

from mpc.adaptive import BiasCorrectedPlantModel, BiasEstimator, BiasState
from mpc.config import AdaptiveConfig
from mpc.state import DisturbanceForecast, PlantRecord


class _PersistenceModel:
    @property
    def min_history_len(self) -> int:
        return 1

    def predict_next(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: float,
        step_seconds: int,
        disturbance: PlantRecord | None = None,
    ) -> float:
        return history[-1].soil_moisture - 1.0

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
        for _ in pump_seconds:
            current -= 1.0
            values.append(current)
        return tuple(values)


def test_bias_estimator_accepts_recent_residuals_and_clips_bias() -> None:
    estimator = BiasEstimator(
        AdaptiveConfig(enabled=True, bias_window=2, max_abs_bias=3.0),
        stale_after_seconds=600,
    )
    now = datetime(2026, 5, 9, 10, 0, tzinfo=timezone.utc)

    first = estimator.observe(
        BiasState(),
        predicted=55.0,
        observed=58.0,
        observed_at=now,
        now=now,
    )
    second = estimator.observe(
        first.state,
        predicted=55.0,
        observed=65.0,
        observed_at=now,
        now=now,
    )

    assert first.accepted is True
    assert first.state.current_bias == pytest.approx(3.0)
    assert second.accepted is False
    assert second.reason == "outlier_residual"
    assert second.state == first.state


def test_bias_estimator_ignores_missing_stale_and_disabled_residuals() -> None:
    state = BiasState(current_bias=1.0)
    now = datetime(2026, 5, 9, 10, 0, tzinfo=timezone.utc)
    estimator = BiasEstimator(
        AdaptiveConfig(enabled=True, bias_window=3, max_abs_bias=5.0),
        stale_after_seconds=600,
    )

    missing = estimator.observe(
        state,
        predicted=None,
        observed=58.0,
        observed_at=now,
        now=now,
    )
    stale = estimator.observe(
        state,
        predicted=55.0,
        observed=58.0,
        observed_at=now - timedelta(seconds=601),
        now=now,
    )
    disabled = BiasEstimator(
        AdaptiveConfig(enabled=False),
        stale_after_seconds=600,
    ).observe(
        state,
        predicted=55.0,
        observed=58.0,
        observed_at=now,
        now=now,
    )

    assert missing.reason == "missing_residual"
    assert stale.reason == "stale_residual"
    assert disabled.reason == "disabled"
    assert missing.state == stale.state == disabled.state == state


def test_bias_corrected_plant_model_applies_bias_recursively() -> None:
    model = BiasCorrectedPlantModel(
        _PersistenceModel(),
        bias=1.0,
        state_min=0.0,
        state_max=100.0,
    )
    history = [
        PlantRecord(
            soil_moisture=50.0,
            temperature=27.0,
            humidity=72.0,
            light=300.0,
        )
    ]
    disturbances = DisturbanceForecast(
        temperature=(27.0, 27.0),
        humidity=(72.0, 72.0),
        light=(300.0, 300.0),
    )

    assert model.forecast(
        history,
        pump_seconds=(0.0, 0.0),
        step_seconds=300,
        disturbances=disturbances,
    ) == pytest.approx((50.0, 50.0))
