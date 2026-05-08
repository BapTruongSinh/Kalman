"""Plant model interface used by MPC solvers."""

from __future__ import annotations

from typing import Protocol, Sequence

from mpc.state import DisturbanceForecast, PlantRecord


class PlantModel(Protocol):
    @property
    def min_history_len(self) -> int:
        """Minimum PlantRecord history length needed for prediction."""
        ...

    def predict_next(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: float,
        step_seconds: int,
        disturbance: PlantRecord | None = None,
    ) -> float:
        """Predict the next soil moisture value."""
        ...

    def forecast(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: Sequence[float],
        step_seconds: int,
        disturbances: DisturbanceForecast,
    ) -> tuple[float, ...]:
        """Forecast a sequence of soil moisture values."""
        ...
