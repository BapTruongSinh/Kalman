from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from mpc.config import AdaptiveConfig, ControllerConfig, CostWeights, PumpLimits
from mpc.plant import ARXPlantModel
from mpc.solver.cost import score_fao56_pump_sequence_with_daily_reset
from mpc.simulation import run_adaptive_simulation, run_simulation


def _artifact(path: Path) -> Path:
    artifact_path = path / "arx_model.json"
    artifact_path.write_text(
        json.dumps(
            {
                "model": "ARX",
                "model_config": {
                    "na": 1,
                    "nb": 1,
                    "nk": 1,
                    "include_intercept": False,
                    "input_cols": ["Drip"],
                    "output_col": "Soil_Moisture",
                },
                "theta_hat": [1.0, 2.0],
            }
        ),
        encoding="utf-8",
    )
    return artifact_path


def _below_band_csv(path: Path) -> Path:
    csv_path = path / "below_band_trace.csv"
    rows = [
        "Timestamp,Soil_Moisture,Temperature,Humidity,Light,Drip,Mist,Fan",
        "2026-05-08 10:00:00,0.0,27.0,72.0,300.0,0.0,0.0,0.0",
        "2026-05-08 10:05:00,0.0,27.0,72.0,300.0,0.0,0.0,0.0",
        "2026-05-08 10:10:00,0.0,27.0,72.0,300.0,0.0,0.0,0.0",
        "2026-05-08 10:15:00,0.0,27.0,72.0,300.0,0.0,0.0,0.0",
    ]
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return csv_path


def _positive_bias_csv(path: Path) -> Path:
    csv_path = path / "positive_bias_trace.csv"
    rows = [
        "Timestamp,Soil_Moisture,Temperature,Humidity,Light,Drip,Mist,Fan",
        "2026-05-08 10:00:00,55.0,27.0,72.0,300.0,0.0,0.0,0.0",
        "2026-05-08 10:05:00,60.0,27.0,72.0,300.0,0.0,0.0,0.0",
        "2026-05-08 10:10:00,60.0,27.0,72.0,300.0,0.0,0.0,0.0",
        "2026-05-08 10:15:00,60.0,27.0,72.0,300.0,0.0,0.0,0.0",
        "2026-05-08 10:20:00,60.0,27.0,72.0,300.0,0.0,0.0,0.0",
    ]
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return csv_path


def test_simulation_regression_mpc_irrigates_dry_fao_profile(
    tmp_path: Path,
) -> None:
    model = ARXPlantModel.load_artifact(_artifact(tmp_path))
    config = ControllerConfig(
        horizon_steps=2,
        pump=PumpLimits(max_seconds=300.0, grid_seconds=150.0),
        cost=CostWeights(
            band_violation=10.0,
            terminal_band_violation=20.0,
            water_use=1.0,
            switching=0.0,
            daily_cap_excess=0.0,
        ),
    )

    report = run_simulation(
        csv_path=_below_band_csv(tmp_path),
        plant_model=model,
        config=config,
        beam_width=4,
    )
    payload = report.to_dict()
    mpc = payload["controllers"]["mpc"]
    threshold = payload["controllers"]["threshold"]

    assert payload["simulated_steps"] == 3
    assert mpc["total_pump_seconds"] == pytest.approx(900.0)
    assert threshold["total_pump_seconds"] == pytest.approx(900.0)
    assert mpc["switching_count"] == 1
    assert threshold["switching_count"] == 1
    assert mpc["band_violation_steps"] == threshold["band_violation_steps"]
    assert mpc["cost_breakdown"]["water"] == pytest.approx(3.0)
    expected_cost = score_fao56_pump_sequence_with_daily_reset(
        initial_sensor_percent=0.0,
        pump_seconds=(300.0, 300.0, 300.0),
        dates=(date(2026, 5, 8), date(2026, 5, 8), date(2026, 5, 8)),
        previous_pump_seconds=0.0,
        config=config,
    ).cost
    assert mpc["objective_cost"] == pytest.approx(expected_cost.total)
    assert mpc["cost_breakdown"]["band"] == pytest.approx(expected_cost.band)
    assert mpc["cost_breakdown"]["overwater"] == pytest.approx(
        expected_cost.overwater
    )
    assert mpc["objective_cost"] == pytest.approx(threshold["objective_cost"])


def test_adaptive_simulation_reduces_observation_error_on_bias_mismatch(
    tmp_path: Path,
) -> None:
    model = ARXPlantModel.load_artifact(_artifact(tmp_path))
    config = ControllerConfig(
        horizon_steps=1,
        pump=PumpLimits(max_seconds=300.0, grid_seconds=300.0),
        adaptive=AdaptiveConfig(
            enabled=True,
            bias_window=1,
            max_abs_bias=5.0,
        ),
    )

    report = run_adaptive_simulation(
        csv_path=_positive_bias_csv(tmp_path),
        plant_model=model,
        config=config,
        beam_width=2,
    )
    payload = report.to_dict()
    mpc = payload["controllers"]["mpc"]
    ampc = payload["controllers"]["ampc"]

    assert set(payload["controllers"]) == {"mpc", "ampc", "threshold"}
    assert ampc["mean_absolute_observation_error"] < (
        mpc["mean_absolute_observation_error"]
    )
    assert ampc["max_absolute_observation_error"] <= (
        mpc["max_absolute_observation_error"]
    )


def test_adaptive_simulation_enables_bias_when_config_default_is_static(
    tmp_path: Path,
) -> None:
    model = ARXPlantModel.load_artifact(_artifact(tmp_path))
    config = ControllerConfig(
        horizon_steps=1,
        pump=PumpLimits(max_seconds=300.0, grid_seconds=300.0),
    )

    assert config.adaptive.enabled is False
    report = run_adaptive_simulation(
        csv_path=_positive_bias_csv(tmp_path),
        plant_model=model,
        config=config,
        beam_width=2,
    )
    payload = report.to_dict()
    mpc = payload["controllers"]["mpc"]
    ampc = payload["controllers"]["ampc"]

    assert ampc["mean_absolute_observation_error"] < (
        mpc["mean_absolute_observation_error"]
    )


def test_simulation_rejects_csv_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad_trace.csv"
    csv_path.write_text(
        "Timestamp,Soil_Moisture,Temperature,Humidity\n"
        "2026-05-08 10:00:00,54.0,27.0,72.0\n",
        encoding="utf-8",
    )
    model = ARXPlantModel.load_artifact(_artifact(tmp_path))

    with pytest.raises(ValueError, match="missing columns"):
        run_simulation(
            csv_path=csv_path,
            plant_model=model,
            config=ControllerConfig(),
        )
