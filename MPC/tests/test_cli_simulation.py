from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mpc.config import ControllerConfig, SafetyConfig
from mpc.schema import default_config_schema
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


def test_cli_recommend_uses_default_demo_paths() -> None:
    output_path = Path(__file__).resolve().parents[1] / "reports" / "recommendation.json"
    _remove(output_path)

    result = _run_cli("recommend", "--beam-width", "4")

    try:
        assert result.returncode == 0, result.stderr
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["safety_status"] == "safe"
        assert "pump_seconds" in payload
    finally:
        _remove(output_path)


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


def test_cli_simulate_uses_default_artifact_input_and_output() -> None:
    output_path = Path(__file__).resolve().parents[1] / "reports" / "v2_simulation.json"
    _remove(output_path)

    result = _run_cli("simulate", "--max-steps", "1", "--beam-width", "4")

    try:
        assert result.returncode == 0, result.stderr
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["simulated_steps"] == 1
        assert set(payload["controllers"]) == {"mpc", "threshold"}
    finally:
        _remove(output_path)


def test_cli_adaptive_simulate_writes_v2_v3_report_json(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    csv_path = _csv(tmp_path)
    output_path = tmp_path / "adaptive_report.json"

    result = _run_cli(
        "adaptive-simulate",
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
    assert set(payload["controllers"]) == {"mpc", "ampc", "threshold"}
    assert payload["config"]["adaptive"]["enabled"] is True


def test_cli_adaptive_simulate_uses_default_artifact_input_and_output() -> None:
    output_path = (
        Path(__file__).resolve().parents[1]
        / "reports"
        / "v3_adaptive_simulation.json"
    )
    _remove(output_path)

    result = _run_cli("adaptive-simulate", "--max-steps", "1", "--beam-width", "4")

    try:
        assert result.returncode == 0, result.stderr
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["simulated_steps"] == 1
        assert set(payload["controllers"]) == {"mpc", "ampc", "threshold"}
        assert payload["config"]["adaptive"]["enabled"] is True
    finally:
        _remove(output_path)


def test_cli_closed_loop_without_explicit_actuator_config_fails_closed(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path)
    state_path = tmp_path / "state.json"
    config_path = tmp_path / "config.json"
    output_path = tmp_path / "closed_loop.json"
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
    config_path.write_text(json.dumps({}), encoding="utf-8")

    result = _run_cli(
        "closed-loop",
        "--artifact",
        str(artifact),
        "--state-json",
        str(state_path),
        "--config",
        str(config_path),
        "--output",
        str(output_path),
        "--now",
        now.isoformat(),
        "--beam-width",
        "4",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["actuator"]["executed"] is False
    assert payload["actuator"]["status"] == "config_error"
    assert payload["actuator"]["command"]["pump_seconds"] == 0.0
    assert payload["actuator"]["command"]["safety_status"] == "actuator_error"
    assert "actuator_disabled" in payload["alerts"]


def test_cli_auto_uses_defaults_and_fails_closed_without_actuator() -> None:
    output_path = (
        Path(__file__).resolve().parents[1]
        / "reports"
        / "closed_loop_dry_run.json"
    )
    _remove(output_path)

    result = _run_cli("auto", "--beam-width", "4")

    try:
        assert result.returncode == 0, result.stderr
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["actuator"]["executed"] is False
        assert payload["actuator"]["command"]["pump_seconds"] == 0.0
        assert "actuator_disabled" in payload["alerts"]
    finally:
        _remove(output_path)


def test_cli_config_schema_writes_website_loadable_json() -> None:
    result = _run_cli("config-schema")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == default_config_schema()
    assert payload["controller_defaults"]["target_band"] == {
        "low": 55.0,
        "high": 65.0,
    }
    assert payload["runtime_defaults"]["artifact"] == "../ARX/arx_model.json"
    user_fields = {
        field["name"]
        for field in payload["field_groups"]["user_inputs"]
    }
    assert {"target_band.low", "target_band.high", "crop.kc"} <= user_fields


def test_cli_config_schema_can_write_output_file(tmp_path: Path) -> None:
    output_path = tmp_path / "config_schema.json"

    result = _run_cli("config-schema", "--output", str(output_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1


def test_cli_uses_mpc_config_path_env_when_config_arg_is_omitted(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path, drip_gain=0.0)
    state_path = tmp_path / "state.json"
    config_path = tmp_path / "config.json"
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
    config_path.write_text(
        json.dumps({"target_band": {"low": 60.0, "high": 70.0}}),
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
        extra_env={"MPC_CONFIG_PATH": str(config_path)},
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["target_band"] == {"low": 60.0, "high": 70.0}


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


def _run_cli(
    *args: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "mpc", *args],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
