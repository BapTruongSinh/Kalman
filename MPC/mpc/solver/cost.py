"""Cost function for the v2 grid-shooting MPC solver."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from mpc.config import ControllerConfig


@dataclass(frozen=True)
class TrajectoryCost:
    total: float
    band: float
    terminal: float
    water: float
    switching: float
    daily_cap: float


def band_error(value: float, *, low: float, high: float) -> float:
    if value < low:
        return low - value
    if value > high:
        return value - high
    return 0.0


def score_trajectory(
    *,
    predictions: Sequence[float],
    pump_seconds: Sequence[float],
    previous_pump_seconds: float,
    used_today_pump_seconds: float,
    config: ControllerConfig,
) -> TrajectoryCost:
    if len(predictions) != len(pump_seconds):
        raise ValueError("predictions and pump sequence must align")
    if not predictions:
        raise ValueError("trajectory must not be empty")
    if not isfinite(previous_pump_seconds):
        raise ValueError("previous_pump_seconds must be finite")
    if not isfinite(used_today_pump_seconds):
        raise ValueError("used_today_pump_seconds must be finite")
    if used_today_pump_seconds < 0.0:
        raise ValueError("used_today_pump_seconds must be >= 0")

    band_total = 0.0
    water_total = 0.0
    switching_total = 0.0
    daily_cap_total = 0.0
    cumulative_pump = used_today_pump_seconds
    previous_pump = previous_pump_seconds

    for value, pump in zip(predictions, pump_seconds):
        if not isfinite(value):
            raise ValueError("predicted soil moisture must be finite")
        if not isfinite(pump):
            raise ValueError("pump_seconds must be finite")
        if pump < 0.0:
            raise ValueError("pump_seconds must be >= 0")

        error = band_error(
            value,
            low=config.target_band.low,
            high=config.target_band.high,
        )
        pump_ratio = pump / float(config.step_seconds)
        switch_ratio = abs(pump - previous_pump) / float(config.step_seconds)
        cumulative_pump += pump
        daily_excess_ratio = max(
            0.0,
            cumulative_pump - config.safety.soft_daily_pump_cap_seconds,
        ) / float(config.step_seconds)

        band_total += config.cost.band_violation * error * error
        water_total += config.cost.water_use * pump_ratio * pump_ratio
        switching_total += config.cost.switching * switch_ratio * switch_ratio
        daily_cap_total += (
            config.cost.daily_cap_excess
            * daily_excess_ratio
            * daily_excess_ratio
        )
        previous_pump = pump

    terminal_error = band_error(
        predictions[-1],
        low=config.target_band.low,
        high=config.target_band.high,
    )
    terminal_total = (
        config.cost.terminal_band_violation
        * terminal_error
        * terminal_error
    )
    total = (
        band_total
        + water_total
        + switching_total
        + daily_cap_total
        + terminal_total
    )
    return TrajectoryCost(
        total=total,
        band=band_total,
        terminal=terminal_total,
        water=water_total,
        switching=switching_total,
        daily_cap=daily_cap_total,
    )
