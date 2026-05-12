from __future__ import annotations

import math

import pytest

from mpc.config import ControllerConfig, load_controller_config
from mpc.fao56 import (
    FAO56_SOIL_PRESETS,
    Fao56Config,
    adjusted_crop_et_mm,
    advance_depletion_mm,
    depletion_from_theta_mm,
    et0_step_mm,
    fao56_config_from_mapping,
    irrigation_depth_mm,
    readily_available_water_mm,
    sensor_percent_from_theta,
    state_from_sensor_percent,
    theta_from_sensor_percent,
    total_available_water_mm,
    water_stress_coefficient,
)


def test_soil_presets_match_plan() -> None:
    assert FAO56_SOIL_PRESETS == {
        "sand": {"theta_fc": 0.10, "theta_wp": 0.04, "theta_sat": 0.45},
        "light_loam": {
            "theta_fc": 0.15,
            "theta_wp": 0.06,
            "theta_sat": 0.45,
        },
        "loam": {"theta_fc": 0.32, "theta_wp": 0.15, "theta_sat": 0.45},
        "clay_loam": {
            "theta_fc": 0.35,
            "theta_wp": 0.23,
            "theta_sat": 0.45,
        },
    }


def test_loam_sensor_percent_maps_to_theta_and_depletion_terms() -> None:
    config = Fao56Config()

    theta = theta_from_sensor_percent(55.0, config)
    taw = total_available_water_mm(config)
    raw = readily_available_water_mm(config, taw)
    depletion = depletion_from_theta_mm(theta, config, taw)
    state = state_from_sensor_percent(55.0, config)

    assert theta == pytest.approx(0.315)
    assert sensor_percent_from_theta(theta, config) == pytest.approx(55.0)
    assert taw == pytest.approx(51.0)
    assert raw == pytest.approx(25.5)
    assert depletion == pytest.approx(1.5)
    assert state.theta == pytest.approx(theta)
    assert state.depletion_mm == pytest.approx(depletion)


def test_sensor_percent_endpoints_map_to_wet_and_dry_bounds() -> None:
    config = Fao56Config()

    wet_theta = theta_from_sensor_percent(100.0, config)
    dry_theta = theta_from_sensor_percent(0.0, config)

    assert wet_theta == pytest.approx(0.45)
    assert depletion_from_theta_mm(wet_theta, config) == pytest.approx(0.0)
    assert dry_theta == pytest.approx(0.15)
    assert depletion_from_theta_mm(dry_theta, config) == pytest.approx(
        total_available_water_mm(config)
    )


def test_water_stress_coefficient_matches_fao56_thresholds() -> None:
    config = Fao56Config()
    taw = total_available_water_mm(config)
    raw = readily_available_water_mm(config, taw)

    assert water_stress_coefficient(raw, config, taw, raw) == pytest.approx(1.0)
    assert water_stress_coefficient(taw, config, taw, raw) == pytest.approx(0.0)


def test_irrigation_depth_uses_pump_efficiency_flow_time_and_area() -> None:
    config = Fao56Config(
        pump_efficiency=0.8,
        pump_flow_lps=0.02,
        irrigation_area_m2=0.25,
    )

    assert irrigation_depth_mm(300.0, config) == pytest.approx(19.2)


def test_advance_depletion_applies_et_and_irrigation_then_clamps() -> None:
    config = Fao56Config(crop_kc=1.2)

    result = advance_depletion_mm(
        depletion_mm=1.5,
        et0_hour_mm=0.6,
        pump_seconds=300.0,
        step_seconds=300,
        config=config,
    )

    assert result.water_stress_ks == pytest.approx(1.0)
    assert result.et0_step_mm == pytest.approx(0.05)
    assert result.etc_adjusted_mm == pytest.approx(0.06)
    assert result.irrigation_depth_mm == pytest.approx(19.2)
    assert result.depletion_raw_next_mm == pytest.approx(-17.64)
    assert result.depletion_next_mm == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"theta_wp": 0.32}, "theta values"),
        ({"theta_fc": 0.9, "theta_sat": 1.0}, "theta values"),
        ({"root_depth_m": 0.0}, "root_depth_m"),
        ({"depletion_fraction_p": 0.0}, "depletion_fraction_p"),
        ({"depletion_fraction_p": 1.0}, "depletion_fraction_p"),
        ({"et0_hour_mm": -0.1}, "et0_hour_mm"),
        ({"pump_efficiency": 0.0}, "pump_efficiency"),
        ({"pump_efficiency": 1.1}, "pump_efficiency"),
        ({"pump_flow_lps": 0.0}, "pump_flow_lps"),
        ({"irrigation_area_m2": 0.0}, "irrigation_area_m2"),
        ({"soil_type": "clay"}, "soil_type"),
    ],
)
def test_fao56_config_rejects_invalid_physical_values(
    kwargs: dict[str, float | str],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        Fao56Config(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"crop_kc": math.inf},
        {"theta_fc": math.inf},
        {"theta_wp": math.nan},
        {"theta_sat": math.inf},
        {"root_depth_m": math.inf},
        {"depletion_fraction_p": math.nan},
        {"et0_hour_mm": math.inf},
        {"pump_efficiency": math.inf},
        {"pump_flow_lps": math.inf},
        {"irrigation_area_m2": math.nan},
    ],
)
def test_fao56_config_rejects_non_finite_values(
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(ValueError, match="finite"):
        Fao56Config(**kwargs)


def test_fao56_mapping_applies_soil_preset_before_overrides() -> None:
    config = fao56_config_from_mapping(
        {
            "soil_type": "sand",
            "root_depth_m": 0.4,
            "crop_kc": 0.9,
        }
    )

    assert config.soil_type == "sand"
    assert config.theta_fc == pytest.approx(0.10)
    assert config.theta_wp == pytest.approx(0.04)
    assert config.theta_sat == pytest.approx(0.45)
    assert config.root_depth_m == pytest.approx(0.4)
    assert config.crop_kc == pytest.approx(0.9)


def test_fao56_mapping_keeps_preset_theta_when_one_theta_is_overridden() -> None:
    config = fao56_config_from_mapping(
        {
            "soil_type": "clay_loam",
            "theta_fc": 0.36,
        }
    )

    assert config.soil_type == "clay_loam"
    assert config.theta_fc == pytest.approx(0.36)
    assert config.theta_wp == pytest.approx(0.23)
    assert config.theta_sat == pytest.approx(0.45)


def test_controller_config_loads_fao56_section(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
          "fao56": {
            "soil_type": "light_loam",
            "root_depth_m": 0.5,
            "pump_flow_lps": 0.03
          }
        }
        """,
        encoding="utf-8",
    )

    config = load_controller_config(config_path)

    assert isinstance(config, ControllerConfig)
    assert config.fao56.soil_type == "light_loam"
    assert config.fao56.theta_fc == pytest.approx(0.15)
    assert config.fao56.theta_wp == pytest.approx(0.06)
    assert config.fao56.theta_sat == pytest.approx(0.45)
    assert config.fao56.root_depth_m == pytest.approx(0.5)
    assert config.fao56.pump_flow_lps == pytest.approx(0.03)


def test_sensor_percent_is_not_treated_as_direct_theta() -> None:
    config = Fao56Config()

    theta = theta_from_sensor_percent(55.0, config)

    assert theta != 55.0
    assert adjusted_crop_et_mm(
        water_stress_ks=1.0,
        et0_step_mm_value=et0_step_mm(0.6, 300),
        config=config,
    ) == pytest.approx(0.05)


@pytest.mark.parametrize("sensor_percent", [-0.1, 100.1, math.inf, math.nan])
def test_sensor_percent_validation(sensor_percent: float) -> None:
    with pytest.raises(ValueError):
        theta_from_sensor_percent(sensor_percent, Fao56Config())
