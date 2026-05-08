from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mpc.config import ControllerConfig, SafetyConfig
from mpc.plant import ARXPlantModel
from mpc.simulation import run_simulation


def _artifact(path: Path, *, drip_gain: float = 2.0) -> Path:
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
                "theta_hat": [1.0, drip_gain],
            }
        ),
        encoding="utf-8",
    )
    return artifact_path


def _csv(path: Path) -> Path:
    csv_path = path / "trace.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Timestamp,Soil_Moisture,Temperature,Humidity,Light,Drip,Mist,Fan",
                "2026-05-08 10:00:00,54.0,27.0,72.0,300.0,0.0,0.0,0.0",
                "2026-05-08 10:05:00,54.0,27.0,72.0,300.0,0.0,0.0,0.0",
                "2026-05-08 10:10:00,54.0,27.0,72.0,300.0,0.0,0.0,0.0",
                "2026-05-08 10:15:00,54.0,27.0,72.0,300.0,0.0,0.0,0.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def _multi_day_csv(path: Path) -> Path:
    csv_path = path / "multi_day_trace.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Timestamp,Soil_Moisture,Temperature,Humidity,Light,Drip,Mist,Fan",
                "2026-05-08 23:50:00,54.0,27.0,72.0,300.0,0.0,0.0,0.0",
                "2026-05-08 23:55:00,54.0,27.0,72.0,300.0,0.0,0.0,0.0",
                "2026-05-08 23:59:00,54.0,27.0,72.0,300.0,0.0,0.0,0.0",
                "2026-05-09 00:00:00,54.0,27.0,72.0,300.0,0.0,0.0,0.0",
                "2026-05-09 00:05:00,54.0,27.0,72.0,300.0,0.0,0.0,0.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def test_run_simulation_report_contains_mpc_and_threshold_metrics(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path, drip_gain=0.0)
    csv_path = _csv(tmp_path)
    model = ARXPlantModel.load_artifact(artifact)

    report = run_simulation(
        csv_path=csv_path,
        plant_model=model,
        config=ControllerConfig(),
        max_steps=2,
        beam_width=4,
    )
    payload = report.to_dict()

    assert payload["simulated_steps"] == 2
    assert payload["baseline_definition"]["name"] == "threshold_low_full_pump"
    assert set(payload["controllers"]) == {"mpc", "threshold"}
    for metrics in payload["controllers"].values():
        assert set(metrics) >= {
            "band_violation_steps",
            "band_violation_seconds",
            "total_pump_seconds",
            "switching_count",
            "objective_cost",
        }


def test_cli_recommend_writes_recommendation_json(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path, drip_gain=0.0)
    state_path = tmp_path / "state.json"
    output_path = tmp_path / "recommendation.json"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    state_path.write_text(
        json.dumps(
            {
                "timestamp": now.isoformat(),
                "kf_x_posterior": 54.0,
                "temperature": 27.0,
                "humidity": 72.0,
                "light": 300.0,
                "last_pump_seconds": 0.0,
            }
        ),
        encoding="utf-8",
    )

    result = _run_cli(
        "recommend",
        "--artifact",
        str(artifact),
        "--state-json",
        str(state_path),
        "--output",
        str(output_path),
        "--now",
        now.isoformat(),
        "--beam-width",
        "4",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["safety_status"] == "safe"
    assert payload["pump_seconds"] >= 0.0
    assert "recommendation" not in payload
    assert "config" not in payload


def test_cli_simulate_writes_report_json(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    csv_path = _csv(tmp_path)
    output_path = tmp_path / "report.json"

    result = _run_cli(
        "simulate",
        "--artifact",
        str(artifact),
        "--input",
        str(csv_path),
        "--output",
        str(output_path),
        "--max-steps",
        "2",
        "--beam-width",
        "4",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["simulated_steps"] == 2
    assert payload["baseline_definition"]["name"] == "threshold_low_full_pump"
    assert set(payload["controllers"]) == {"mpc", "threshold"}


def test_simulation_daily_cap_cost_resets_by_calendar_day(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path, drip_gain=0.0)
    csv_path = _multi_day_csv(tmp_path)
    model = ARXPlantModel.load_artifact(artifact)
    config = ControllerConfig(
        safety=SafetyConfig(soft_daily_pump_cap_seconds=300.0)
    )

    report = run_simulation(
        csv_path=csv_path,
        plant_model=model,
        config=config,
        beam_width=4,
    )
    threshold = report.to_dict()["controllers"]["threshold"]

    assert threshold["total_pump_seconds"] == pytest.approx(1200.0)
    assert threshold["cost_breakdown"]["daily_cap"] == pytest.approx(4.0)


def test_cli_recommend_invalid_state_exits_nonzero(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    state_path = tmp_path / "bad_state.json"
    output_path = tmp_path / "recommendation.json"
    state_path.write_text("[]", encoding="utf-8")

    result = _run_cli(
        "recommend",
        "--artifact",
        str(artifact),
        "--state-json",
        str(state_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 2
    assert "state JSON root must be an object" in result.stderr
    assert not output_path.exists()


def test_cli_recommend_missing_artifact_exits_nonzero(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    output_path = tmp_path / "recommendation.json"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    state_path.write_text(
        json.dumps(
            {
                "timestamp": now.isoformat(),
                "kf_x_posterior": 54.0,
                "temperature": 27.0,
                "humidity": 72.0,
                "light": 300.0,
                "last_pump_seconds": 0.0,
            }
        ),
        encoding="utf-8",
    )

    result = _run_cli(
        "recommend",
        "--artifact",
        str(tmp_path / "missing_arx_model.json"),
        "--state-json",
        str(state_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 2
    assert "ARX artifact not found" in result.stderr
    assert not output_path.exists()


def test_cli_simulate_invalid_config_exits_nonzero(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    csv_path = _csv(tmp_path)
    config_path = tmp_path / "bad_config.json"
    output_path = tmp_path / "report.json"
    config_path.write_text(
        json.dumps({"pump": {"grid_seconds": 301.0}}),
        encoding="utf-8",
    )

    result = _run_cli(
        "simulate",
        "--artifact",
        str(artifact),
        "--input",
        str(csv_path),
        "--output",
        str(output_path),
        "--config",
        str(config_path),
    )

    assert result.returncode == 2
    assert "pump.grid_seconds" in result.stderr
    assert not output_path.exists()


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    return subprocess.run(
        [sys.executable, "-m", "mpc", *args],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
