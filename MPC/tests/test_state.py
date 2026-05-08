from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mpc.state import ControllerState, DisturbanceForecast


def test_controller_state_prefers_kalman_posterior() -> None:
    state = ControllerState(
        timestamp=datetime.now(timezone.utc),
        kf_x_posterior=58.0,
        raw_soil_moisture=41.0,
        temperature=27.0,
        humidity=72.0,
        light=300.0,
    )

    assert state.soil_moisture == 58.0


def test_controller_state_falls_back_to_raw_soil_moisture() -> None:
    state = ControllerState(
        timestamp=datetime.now(timezone.utc),
        raw_soil_moisture=41.0,
        temperature=27.0,
        humidity=72.0,
        light=300.0,
    )

    assert state.soil_moisture == 41.0


def test_controller_state_requires_a_soil_moisture_source() -> None:
    state = ControllerState(
        timestamp=datetime.now(timezone.utc),
        temperature=27.0,
        humidity=72.0,
        light=300.0,
    )

    with pytest.raises(ValueError, match="kf_x_posterior or raw"):
        _ = state.soil_moisture


def test_controller_state_from_mapping_validates_last_pump_seconds() -> None:
    with pytest.raises(ValueError, match="last_pump_seconds"):
        ControllerState.from_mapping(
            {
                "timestamp": "2026-05-08T10:00:00Z",
                "raw_soil_moisture": 55.0,
                "temperature": 27.0,
                "humidity": 72.0,
                "light": 300.0,
                "last_pump_seconds": None,
            }
        )


def test_controller_state_from_mapping_validates_run_id() -> None:
    with pytest.raises(ValueError, match="run_id"):
        ControllerState.from_mapping(
            {
                "timestamp": "2026-05-08T10:00:00Z",
                "raw_soil_moisture": 55.0,
                "temperature": 27.0,
                "humidity": 72.0,
                "light": 300.0,
                "run_id": "1",
            }
        )


def test_measured_hold_forecast_repeats_disturbances() -> None:
    state = ControllerState(
        timestamp=datetime.now(timezone.utc),
        raw_soil_moisture=55.0,
        temperature=27.0,
        humidity=72.0,
        light=300.0,
    )

    forecast = DisturbanceForecast.measured_hold(state, 3)

    assert forecast.temperature == (27.0, 27.0, 27.0)
    assert forecast.humidity == (72.0, 72.0, 72.0)
    assert forecast.light == (300.0, 300.0, 300.0)
