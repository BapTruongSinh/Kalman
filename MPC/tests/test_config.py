from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from mpc.config import (
    ActuatorConfig,
    AdaptiveConfig,
    ControllerConfig,
    PumpLimits,
    SafetyConfig,
    TargetBand,
    load_controller_config,
)


def test_controller_config_defaults_match_v2_contract() -> None:
    config = ControllerConfig()

    assert config.step_seconds == 300
    assert config.horizon_steps == 12
    assert config.target_band == TargetBand(low=55.0, high=65.0)
    assert config.adaptive == AdaptiveConfig(
        enabled=False,
        bias_window=12,
        max_abs_bias=5.0,
    )
    assert config.actuator == ActuatorConfig(
        enabled=False,
        url=None,
        bearer_token_env=None,
        timeout_seconds=5.0,
    )
    assert config.pump.candidates() == (
        0.0,
        30.0,
        60.0,
        90.0,
        120.0,
        150.0,
        180.0,
        210.0,
        240.0,
        270.0,
        300.0,
    )


@pytest.mark.parametrize(
    ("factory", "match"),
    [
        (
            lambda: ControllerConfig(
                target_band=TargetBand(low=65.0, high=65.0)
            ),
            "target band",
        ),
        (
            lambda: ControllerConfig(
                pump=PumpLimits(max_seconds=300.0, grid_seconds=301.0)
            ),
            "grid",
        ),
        (
            lambda: ControllerConfig(
                safety=SafetyConfig(fail_closed_pump_seconds=1.0)
            ),
            "fail-closed",
        ),
        (
            lambda: ControllerConfig(
                safety=SafetyConfig(soft_daily_pump_cap_seconds=0.0)
            ),
            "soft daily cap",
        ),
        (
            lambda: ControllerConfig(
                adaptive=AdaptiveConfig(bias_window=0)
            ),
            "bias_window",
        ),
        (
            lambda: ControllerConfig(
                adaptive=AdaptiveConfig(enabled="true")
            ),
            "enabled",
        ),
        (
            lambda: ControllerConfig(
                actuator=ActuatorConfig(enabled="true")
            ),
            "actuator.enabled",
        ),
        (
            lambda: ControllerConfig(
                actuator=ActuatorConfig(url="")
            ),
            "actuator.url",
        ),
        (
            lambda: ControllerConfig(
                actuator=ActuatorConfig(timeout_seconds=0.0)
            ),
            "timeout",
        ),
        (lambda: ControllerConfig(step_seconds=0), "step_seconds"),
        (lambda: ControllerConfig(horizon_steps=0), "horizon_steps"),
    ],
)
def test_controller_config_rejects_invalid_values(
    factory: Callable[[], ControllerConfig],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        factory()


def test_load_controller_config_reads_partial_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "horizon_steps": 3,
                "target_band": {"low": 50.0, "high": 60.0},
                "pump": {"max_seconds": 120.0, "grid_seconds": 60.0},
                "safety": {"soft_daily_pump_cap_seconds": 600.0},
                "adaptive": {
                    "enabled": True,
                    "bias_window": 4,
                    "max_abs_bias": 2.5,
                },
                "actuator": {
                    "enabled": True,
                    "url": "http://127.0.0.1:8000/actuator",
                    "bearer_token_env": "MPC_ACTUATOR_TOKEN",
                    "timeout_seconds": 2.5,
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_controller_config(config_path)

    assert config.horizon_steps == 3
    assert config.target_band.low == 50.0
    assert config.target_band.high == 60.0
    assert config.pump.candidates() == (0.0, 60.0, 120.0)
    assert config.safety.soft_daily_pump_cap_seconds == 600.0
    assert config.adaptive.enabled is True
    assert config.adaptive.bias_window == 4
    assert config.adaptive.max_abs_bias == 2.5
    assert config.actuator.enabled is True
    assert config.actuator.url == "http://127.0.0.1:8000/actuator"
    assert config.actuator.bearer_token_env == "MPC_ACTUATOR_TOKEN"
    assert config.actuator.timeout_seconds == 2.5


def test_load_controller_config_rejects_non_object_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="config JSON root"):
        load_controller_config(config_path)


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"step_seconds": 300.9}, "step_seconds"),
        ({"horizon_steps": 12.1}, "horizon_steps"),
        ({"safety": {"stale_after_seconds": 600.5}}, "stale_after_seconds"),
        ({"adaptive": {"bias_window": 12.5}}, "adaptive.bias_window"),
        ({"adaptive": {"enabled": "true"}}, "adaptive.enabled"),
        ({"actuator": {"enabled": "true"}}, "actuator.enabled"),
        ({"actuator": {"url": ""}}, "actuator.url"),
        ({"step_seconds": "300"}, "step_seconds"),
        ({"horizon_steps": True}, "horizon_steps"),
    ],
)
def test_load_controller_config_rejects_non_integer_fields(
    tmp_path: Path,
    payload: dict[str, object],
    match: str,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=match):
        load_controller_config(config_path)
