from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mpc.config import PumpLimits
from mpc.plant import ARXArtifactConfig, ARXPlantModel
from mpc.state import ControllerState, DisturbanceForecast, PlantRecord

ARTIFACT = Path(__file__).resolve().parents[2] / "ARX" / "arx_model.json"


def _history(n: int = 4) -> list[PlantRecord]:
    return [
        PlantRecord(
            soil_moisture=56.0 + i * 0.1,
            temperature=27.0,
            humidity=72.0,
            light=300.0,
            drip=0.0,
            mist=0.0,
            fan=0.0,
        )
        for i in range(n)
    ]


def test_load_repo_arx_artifact_validates_config_and_coefficients() -> None:
    model = ARXPlantModel.load_artifact(ARTIFACT)

    assert model.config.output_col == "Soil_Moisture"
    assert "Drip" in model.config.input_cols
    assert len(model.theta) == len(model.config.param_names())
    assert model.min_history_len >= 1


def test_predict_next_maps_pump_seconds_to_drip_duty() -> None:
    model = ARXPlantModel.load_artifact(ARTIFACT)
    history = _history(max(model.min_history_len, 4))
    no_pump = model.predict_next(
        history,
        pump_seconds=0.0,
        step_seconds=300,
    )
    full_pump = model.predict_next(
        history,
        pump_seconds=300.0,
        step_seconds=300,
    )

    assert full_pump > no_pump


def test_predict_next_uses_real_output_lags_and_current_control() -> None:
    config = ARXArtifactConfig(
        na=2,
        nb=1,
        nk=1,
        include_intercept=False,
        input_cols=("Drip",),
        output_col="Soil_Moisture",
    )
    model = ARXPlantModel(config=config, theta=(0.0, 1.0, 0.0))
    history = [
        PlantRecord(
            soil_moisture=10.0,
            temperature=27.0,
            humidity=72.0,
            light=300.0,
        ),
        PlantRecord(
            soil_moisture=20.0,
            temperature=27.0,
            humidity=72.0,
            light=300.0,
        ),
    ]

    value = model.predict_next(history, pump_seconds=300.0, step_seconds=300)

    assert value == pytest.approx(10.0)


def test_predict_next_uses_previous_input_for_nb_greater_than_one() -> None:
    config = ARXArtifactConfig(
        na=1,
        nb=2,
        nk=1,
        include_intercept=False,
        input_cols=("Drip",),
        output_col="Soil_Moisture",
    )
    model = ARXPlantModel(config=config, theta=(0.0, 0.0, 1.0))
    history = [
        PlantRecord(
            soil_moisture=10.0,
            temperature=27.0,
            humidity=72.0,
            light=300.0,
            drip=0.25,
        ),
        PlantRecord(
            soil_moisture=20.0,
            temperature=27.0,
            humidity=72.0,
            light=300.0,
            drip=0.75,
        ),
    ]

    value = model.predict_next(history, pump_seconds=300.0, step_seconds=300)

    assert value == pytest.approx(0.75)


def test_forecast_returns_horizon_and_does_not_mutate_history() -> None:
    model = ARXPlantModel.load_artifact(ARTIFACT)
    history = _history(max(model.min_history_len, 4))
    original_len = len(history)
    state = ControllerState(
        timestamp=datetime.now(timezone.utc),
        kf_x_posterior=history[-1].soil_moisture,
        temperature=history[-1].temperature,
        humidity=history[-1].humidity,
        light=history[-1].light,
    )
    forecast = DisturbanceForecast.measured_hold(state, 3)

    values = model.forecast(
        history,
        pump_seconds=(0.0, 30.0, 60.0),
        step_seconds=300,
        disturbances=forecast,
    )

    assert len(values) == 3
    assert len(history) == original_len
    assert all(isinstance(value, float) for value in values)


def test_invalid_artifact_missing_theta_raises(tmp_path: Path) -> None:
    bad_artifact = tmp_path / "bad_arx.json"
    bad_artifact.write_text(
        json.dumps(
            {
                "model": "ARX",
                "model_config": {
                    "na": 1,
                    "nb": 1,
                    "nk": 1,
                    "input_cols": ["Drip"],
                    "output_col": "Soil_Moisture",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="theta_hat"):
        ARXPlantModel.load_artifact(bad_artifact)


def test_custom_pump_limits_clamp_to_bounds() -> None:
    model = ARXPlantModel.load_artifact(
        ARTIFACT,
        pump_limits=PumpLimits(max_seconds=300.0),
    )
    history = _history(max(model.min_history_len, 4))

    at_limit = model.predict_next(history, pump_seconds=300.0, step_seconds=300)
    over_limit = model.predict_next(history, pump_seconds=999.0, step_seconds=300)

    assert over_limit == pytest.approx(at_limit)
