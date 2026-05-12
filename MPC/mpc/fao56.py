"""FAO-56 water-balance primitives for MPC integration.

The capacitive sensor state remains a 0-100 percent signal. This module maps
that signal into volumetric water content before computing FAO depletion terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Mapping


FAO56_SOIL_PRESETS: dict[str, dict[str, float]] = {
    "sand": {
        "theta_fc": 0.10,
        "theta_wp": 0.04,
        "theta_sat": 0.45,
    },
    "light_loam": {
        "theta_fc": 0.15,
        "theta_wp": 0.06,
        "theta_sat": 0.45,
    },
    "loam": {
        "theta_fc": 0.32,
        "theta_wp": 0.15,
        "theta_sat": 0.45,
    },
    "clay_loam": {
        "theta_fc": 0.35,
        "theta_wp": 0.23,
        "theta_sat": 0.45,
    },
}


@dataclass(frozen=True)
class Fao56Config:
    crop_kc: float = 1.0
    soil_type: str = "loam"
    theta_fc: float = FAO56_SOIL_PRESETS["loam"]["theta_fc"]
    theta_wp: float = FAO56_SOIL_PRESETS["loam"]["theta_wp"]
    theta_sat: float = FAO56_SOIL_PRESETS["loam"]["theta_sat"]
    root_depth_m: float = 0.3
    depletion_fraction_p: float = 0.5
    et0_hour_mm: float = 0.6
    pump_efficiency: float = 0.8
    pump_flow_lps: float = 0.02
    irrigation_area_m2: float = 0.25

    def __post_init__(self) -> None:
        if self.soil_type not in FAO56_SOIL_PRESETS:
            allowed = ", ".join(sorted(FAO56_SOIL_PRESETS))
            raise ValueError(f"soil_type must be one of: {allowed}")
        for name, value in (
            ("crop_kc", self.crop_kc),
            ("theta_fc", self.theta_fc),
            ("theta_wp", self.theta_wp),
            ("theta_sat", self.theta_sat),
            ("root_depth_m", self.root_depth_m),
            ("depletion_fraction_p", self.depletion_fraction_p),
            ("et0_hour_mm", self.et0_hour_mm),
            ("pump_efficiency", self.pump_efficiency),
            ("pump_flow_lps", self.pump_flow_lps),
            ("irrigation_area_m2", self.irrigation_area_m2),
        ):
            _require_finite(name, value)

        if self.crop_kc < 0.0:
            raise ValueError("crop_kc must be >= 0")
        if not (0.0 <= self.theta_wp < self.theta_fc < self.theta_sat <= 0.8):
            raise ValueError(
                "theta values must satisfy 0 <= theta_wp < theta_fc "
                "< theta_sat <= 0.8"
            )
        if self.root_depth_m <= 0.0:
            raise ValueError("root_depth_m must be > 0")
        if not (0.0 < self.depletion_fraction_p < 1.0):
            raise ValueError("depletion_fraction_p must satisfy 0 < p < 1")
        if self.et0_hour_mm < 0.0:
            raise ValueError("et0_hour_mm must be >= 0")
        if not (0.0 < self.pump_efficiency <= 1.0):
            raise ValueError("pump_efficiency must satisfy 0 < eta <= 1")
        if self.pump_flow_lps <= 0.0:
            raise ValueError("pump_flow_lps must be > 0")
        if self.irrigation_area_m2 <= 0.0:
            raise ValueError("irrigation_area_m2 must be > 0")

    @classmethod
    def from_soil_preset(
        cls,
        soil_type: str,
        **overrides: float | str,
    ) -> "Fao56Config":
        preset = soil_preset(soil_type)
        return cls(soil_type=soil_type, **{**preset, **overrides})


@dataclass(frozen=True)
class Fao56State:
    sensor_percent: float
    theta: float
    taw_mm: float
    raw_mm: float
    depletion_mm: float
    water_stress_ks: float


@dataclass(frozen=True)
class Fao56Step:
    depletion_raw_next_mm: float
    depletion_next_mm: float
    water_stress_ks: float
    et0_step_mm: float
    etc_adjusted_mm: float
    irrigation_depth_mm: float


def soil_preset(soil_type: str) -> dict[str, float]:
    try:
        return dict(FAO56_SOIL_PRESETS[soil_type])
    except KeyError as exc:
        allowed = ", ".join(sorted(FAO56_SOIL_PRESETS))
        raise ValueError(f"soil_type must be one of: {allowed}") from exc


def fao56_config_from_mapping(payload: Mapping[str, object] | None) -> Fao56Config:
    if payload is None:
        return Fao56Config()
    if not isinstance(payload, Mapping):
        raise ValueError("fao56 must be an object")

    soil_type = payload.get("soil_type", "loam")
    if not isinstance(soil_type, str):
        raise ValueError("fao56.soil_type must be a string")

    overrides: dict[str, float | str] = {}
    for key in (
        "crop_kc",
        "theta_fc",
        "theta_wp",
        "theta_sat",
        "root_depth_m",
        "depletion_fraction_p",
        "et0_hour_mm",
        "pump_efficiency",
        "pump_flow_lps",
        "irrigation_area_m2",
    ):
        if key in payload:
            overrides[key] = _required_float(payload[key], f"fao56.{key}")

    return Fao56Config.from_soil_preset(soil_type, **overrides)


def theta_from_sensor_percent(sensor_percent: float, config: Fao56Config) -> float:
    _require_finite("sensor_percent", sensor_percent)
    if not (0.0 <= sensor_percent <= 100.0):
        raise ValueError("sensor_percent must satisfy 0 <= S <= 100")
    return config.theta_wp + (sensor_percent / 100.0) * (
        config.theta_sat - config.theta_wp
    )


def sensor_percent_from_theta(theta: float, config: Fao56Config) -> float:
    _require_finite("theta", theta)
    return 100.0 * (theta - config.theta_wp) / (
        config.theta_sat - config.theta_wp
    )


def theta_from_depletion_mm(depletion_mm: float, config: Fao56Config) -> float:
    _require_finite("depletion_mm", depletion_mm)
    return config.theta_fc - (depletion_mm / (1000.0 * config.root_depth_m))


def sensor_percent_from_depletion_mm(
    depletion_mm: float,
    config: Fao56Config,
) -> float:
    return sensor_percent_from_theta(
        theta_from_depletion_mm(depletion_mm, config),
        config,
    )


def total_available_water_mm(config: Fao56Config) -> float:
    return 1000.0 * (config.theta_fc - config.theta_wp) * config.root_depth_m


def readily_available_water_mm(
    config: Fao56Config,
    taw_mm: float | None = None,
) -> float:
    taw = total_available_water_mm(config) if taw_mm is None else taw_mm
    _require_finite("taw_mm", taw)
    if taw <= 0.0:
        raise ValueError("taw_mm must be > 0")
    return config.depletion_fraction_p * taw


def depletion_from_theta_mm(
    theta: float,
    config: Fao56Config,
    taw_mm: float | None = None,
) -> float:
    _require_finite("theta", theta)
    taw = total_available_water_mm(config) if taw_mm is None else taw_mm
    _require_finite("taw_mm", taw)
    depletion_raw = 1000.0 * (config.theta_fc - theta) * config.root_depth_m
    return clamp(depletion_raw, 0.0, taw)


def water_stress_coefficient(
    depletion_mm: float,
    config: Fao56Config,
    taw_mm: float | None = None,
    raw_mm: float | None = None,
) -> float:
    _require_finite("depletion_mm", depletion_mm)
    taw = total_available_water_mm(config) if taw_mm is None else taw_mm
    raw = readily_available_water_mm(config, taw) if raw_mm is None else raw_mm
    _require_finite("taw_mm", taw)
    _require_finite("raw_mm", raw)
    if taw <= 0.0:
        raise ValueError("taw_mm must be > 0")
    if raw < 0.0:
        raise ValueError("raw_mm must be >= 0")
    if depletion_mm <= raw:
        return 1.0
    return clamp(
        (taw - depletion_mm) / ((1.0 - config.depletion_fraction_p) * taw),
        0.0,
        1.0,
    )


def et0_step_mm(et0_hour_mm: float, step_seconds: int | float) -> float:
    _require_finite("et0_hour_mm", et0_hour_mm)
    _require_finite("step_seconds", step_seconds)
    step_seconds_float = float(step_seconds)
    if step_seconds_float < 0:
        raise ValueError("step_seconds must be >= 0")
    if et0_hour_mm < 0.0:
        raise ValueError("et0_hour_mm must be >= 0")
    return et0_hour_mm * step_seconds_float / 3600.0


def adjusted_crop_et_mm(
    water_stress_ks: float,
    et0_step_mm_value: float,
    config: Fao56Config,
) -> float:
    _require_finite("water_stress_ks", water_stress_ks)
    _require_finite("et0_step_mm", et0_step_mm_value)
    if not (0.0 <= water_stress_ks <= 1.0):
        raise ValueError("water_stress_ks must satisfy 0 <= Ks <= 1")
    if et0_step_mm_value < 0.0:
        raise ValueError("et0_step_mm must be >= 0")
    return water_stress_ks * config.crop_kc * et0_step_mm_value


def irrigation_depth_mm(pump_seconds: float, config: Fao56Config) -> float:
    _require_finite("pump_seconds", pump_seconds)
    if pump_seconds < 0.0:
        raise ValueError("pump_seconds must be >= 0")
    liters = config.pump_efficiency * config.pump_flow_lps * pump_seconds
    return liters / config.irrigation_area_m2


def advance_depletion_mm(
    depletion_mm: float,
    et0_hour_mm: float,
    pump_seconds: float,
    step_seconds: int | float,
    config: Fao56Config,
) -> Fao56Step:
    taw = total_available_water_mm(config)
    raw = readily_available_water_mm(config, taw)
    current_depletion = clamp_checked(
        depletion_mm,
        0.0,
        taw,
        "depletion_mm",
    )
    ks = water_stress_coefficient(current_depletion, config, taw, raw)
    step_et0 = et0_step_mm(et0_hour_mm, step_seconds)
    adjusted_et = adjusted_crop_et_mm(ks, step_et0, config)
    irrigation = irrigation_depth_mm(pump_seconds, config)
    depletion_raw_next = current_depletion + adjusted_et - irrigation
    depletion_next = clamp(depletion_raw_next, 0.0, taw)
    return Fao56Step(
        depletion_raw_next_mm=depletion_raw_next,
        depletion_next_mm=depletion_next,
        water_stress_ks=ks,
        et0_step_mm=step_et0,
        etc_adjusted_mm=adjusted_et,
        irrigation_depth_mm=irrigation,
    )


def state_from_sensor_percent(
    sensor_percent: float,
    config: Fao56Config,
) -> Fao56State:
    theta = theta_from_sensor_percent(sensor_percent, config)
    taw = total_available_water_mm(config)
    raw = readily_available_water_mm(config, taw)
    depletion = depletion_from_theta_mm(theta, config, taw)
    ks = water_stress_coefficient(depletion, config, taw, raw)
    return Fao56State(
        sensor_percent=sensor_percent,
        theta=theta,
        taw_mm=taw,
        raw_mm=raw,
        depletion_mm=depletion,
        water_stress_ks=ks,
    )


def clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def clamp_checked(
    value: float,
    lower: float,
    upper: float,
    field_name: str,
) -> float:
    _require_finite(field_name, value)
    if value < lower or value > upper:
        raise ValueError(f"{field_name} must satisfy {lower} <= value <= {upper}")
    return value


def _required_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc
    _require_finite(field_name, result)
    return result


def _require_finite(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be finite")
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
