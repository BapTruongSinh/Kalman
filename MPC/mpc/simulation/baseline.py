"""Threshold baseline controller used by v2 simulation reports."""

from __future__ import annotations

from mpc.config import ControllerConfig


BASELINE_NAME = "threshold_low_full_pump"


def threshold_baseline_pump_seconds(
    soil_moisture: float,
    config: ControllerConfig,
) -> float:
    if soil_moisture < config.target_band.low:
        return config.pump.max_seconds
    return config.pump.min_seconds


def baseline_definition(config: ControllerConfig) -> dict[str, object]:
    return {
        "name": BASELINE_NAME,
        "rule": (
            "pump max_seconds when soil_moisture is below target_band.low; "
            "otherwise pump min_seconds"
        ),
        "target_band": {
            "low": config.target_band.low,
            "high": config.target_band.high,
        },
        "pump_seconds_below_low": config.pump.max_seconds,
        "pump_seconds_at_or_above_low": config.pump.min_seconds,
    }
