from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from mpc.config import (
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
