"""Controller configuration contracts for MPC v2/v3."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from typing import Any, Mapping

from .fao56 import Fao56Config, fao56_config_from_mapping


def _require_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class TargetBand:
    low: float = 55.0
    high: float = 65.0

    def __post_init__(self) -> None:
        _require_finite("target_band.low", self.low)
        _require_finite("target_band.high", self.high)
        if not (0.0 <= self.low < self.high <= 100.0):
            raise ValueError(
                "target band must satisfy 0 <= low < high <= 100"
            )


@dataclass(frozen=True)
class PumpLimits:
    min_seconds: float = 0.0
    max_seconds: float = 300.0
    grid_seconds: float = 30.0

    def __post_init__(self) -> None:
        for name, value in (
            ("pump.min_seconds", self.min_seconds),
            ("pump.max_seconds", self.max_seconds),
            ("pump.grid_seconds", self.grid_seconds),
        ):
            _require_finite(name, value)
        if self.min_seconds < 0.0:
            raise ValueError("pump.min_seconds must be >= 0")
        if self.max_seconds <= self.min_seconds:
            raise ValueError("pump.max_seconds must be > pump.min_seconds")
        if self.grid_seconds <= 0.0:
            raise ValueError("pump.grid_seconds must be > 0")
        if self.grid_seconds > self.max_seconds:
            raise ValueError("pump.grid_seconds must be <= pump.max_seconds")

    def clamp(self, pump_seconds: float) -> float:
        _require_finite("pump_seconds", pump_seconds)
        return min(max(pump_seconds, self.min_seconds), self.max_seconds)

    def to_duty(self, pump_seconds: float, step_seconds: int) -> float:
        if step_seconds <= 0:
            raise ValueError("step_seconds must be > 0")
        return self.clamp(pump_seconds) / float(step_seconds)

    def candidates(self) -> tuple[float, ...]:
        values: list[float] = []
        current = self.min_seconds
        epsilon = self.grid_seconds / 1_000_000.0
        while current <= self.max_seconds + epsilon:
            values.append(round(self.clamp(current), 10))
            current += self.grid_seconds
        if values[-1] != self.max_seconds:
            values.append(self.max_seconds)
        return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class CostWeights:
    band_violation: float = 10.0
    terminal_band_violation: float = 20.0
    water_use: float = 0.2
    switching: float = 0.5
    daily_cap_excess: float = 2.0

    def __post_init__(self) -> None:
        for name, value in (
            ("cost.band_violation", self.band_violation),
            ("cost.terminal_band_violation", self.terminal_band_violation),
            ("cost.water_use", self.water_use),
            ("cost.switching", self.switching),
            ("cost.daily_cap_excess", self.daily_cap_excess),
        ):
            _require_finite(name, value)
            if value < 0.0:
                raise ValueError(f"{name} must be >= 0")


@dataclass(frozen=True)
class SafetyConfig:
    state_min: float = 0.0
    state_max: float = 100.0
    stale_after_seconds: int = 600
    soft_daily_pump_cap_seconds: float = 1800.0
    fail_closed_pump_seconds: float = 0.0

    def __post_init__(self) -> None:
        _require_finite("safety.state_min", self.state_min)
        _require_finite("safety.state_max", self.state_max)
        _require_finite(
            "safety.soft_daily_pump_cap_seconds",
            self.soft_daily_pump_cap_seconds,
        )
        _require_finite(
            "safety.fail_closed_pump_seconds",
            self.fail_closed_pump_seconds,
        )
        if self.state_min >= self.state_max:
            raise ValueError("safety.state_min must be < safety.state_max")
        if self.stale_after_seconds <= 0:
            raise ValueError("safety.stale_after_seconds must be > 0")
        if self.soft_daily_pump_cap_seconds <= 0.0:
            raise ValueError("soft daily cap must be > 0")
        if self.fail_closed_pump_seconds != 0.0:
            raise ValueError("fail-closed pump command must remain 0 seconds")


@dataclass(frozen=True)
class AdaptiveConfig:
    enabled: bool = False
    bias_window: int = 12
    max_abs_bias: float = 5.0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("adaptive.enabled must be a boolean")
        if isinstance(self.bias_window, bool) or not isinstance(
            self.bias_window,
            int,
        ):
            raise ValueError("adaptive.bias_window must be an integer")
        if self.bias_window < 1:
            raise ValueError("adaptive.bias_window must be >= 1")
        _require_finite("adaptive.max_abs_bias", self.max_abs_bias)
        if self.max_abs_bias < 0.0:
            raise ValueError("adaptive.max_abs_bias must be >= 0")


@dataclass(frozen=True)
class ActuatorConfig:
    enabled: bool = False
    url: str | None = None
    bearer_token_env: str | None = None
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("actuator.enabled must be a boolean")
        if self.url is not None and not _non_empty_string(self.url):
            raise ValueError("actuator.url must be a non-empty string or null")
        if self.bearer_token_env is not None and not _non_empty_string(
            self.bearer_token_env,
        ):
            raise ValueError(
                "actuator.bearer_token_env must be a non-empty string or null"
            )
        _require_finite("actuator.timeout_seconds", self.timeout_seconds)
        if self.timeout_seconds <= 0.0:
            raise ValueError("actuator.timeout_seconds must be > 0")


@dataclass(frozen=True)
class ControllerConfig:
    step_seconds: int = 300
    horizon_steps: int = 12
    target_band: TargetBand = field(default_factory=TargetBand)
    pump: PumpLimits = field(default_factory=PumpLimits)
    cost: CostWeights = field(default_factory=CostWeights)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    fao56: Fao56Config = field(default_factory=Fao56Config)
    adaptive: AdaptiveConfig = field(default_factory=AdaptiveConfig)
    actuator: ActuatorConfig = field(default_factory=ActuatorConfig)

    def __post_init__(self) -> None:
        if self.step_seconds <= 0:
            raise ValueError("step_seconds must be > 0")
        if self.horizon_steps < 1:
            raise ValueError("horizon_steps must be >= 1")


def controller_config_from_mapping(
    payload: Mapping[str, Any],
) -> ControllerConfig:
    target_raw = _mapping_or_empty(payload.get("target_band"), "target_band")
    pump_raw = _mapping_or_empty(payload.get("pump"), "pump")
    cost_raw = _mapping_or_empty(payload.get("cost"), "cost")
    safety_raw = _mapping_or_empty(payload.get("safety"), "safety")
    fao56_raw = _mapping_or_empty(payload.get("fao56"), "fao56")
    adaptive_raw = _mapping_or_empty(payload.get("adaptive"), "adaptive")
    actuator_raw = _mapping_or_empty(payload.get("actuator"), "actuator")

    return ControllerConfig(
        step_seconds=_strict_int(
            payload.get("step_seconds", 300),
            "step_seconds",
        ),
        horizon_steps=_strict_int(
            payload.get("horizon_steps", 12),
            "horizon_steps",
        ),
        target_band=TargetBand(
            low=float(target_raw.get("low", 55.0)),
            high=float(target_raw.get("high", 65.0)),
        ),
        pump=PumpLimits(
            min_seconds=float(pump_raw.get("min_seconds", 0.0)),
            max_seconds=float(pump_raw.get("max_seconds", 300.0)),
            grid_seconds=float(pump_raw.get("grid_seconds", 30.0)),
        ),
        cost=CostWeights(
            band_violation=float(cost_raw.get("band_violation", 10.0)),
            terminal_band_violation=float(
                cost_raw.get("terminal_band_violation", 20.0)
            ),
            water_use=float(cost_raw.get("water_use", 0.2)),
            switching=float(cost_raw.get("switching", 0.5)),
            daily_cap_excess=float(cost_raw.get("daily_cap_excess", 2.0)),
        ),
        safety=SafetyConfig(
            state_min=float(safety_raw.get("state_min", 0.0)),
            state_max=float(safety_raw.get("state_max", 100.0)),
            stale_after_seconds=_strict_int(
                safety_raw.get("stale_after_seconds", 600),
                "safety.stale_after_seconds",
            ),
            soft_daily_pump_cap_seconds=float(
                safety_raw.get("soft_daily_pump_cap_seconds", 1800.0)
            ),
            fail_closed_pump_seconds=float(
                safety_raw.get("fail_closed_pump_seconds", 0.0)
            ),
        ),
        fao56=fao56_config_from_mapping(fao56_raw),
        adaptive=AdaptiveConfig(
            enabled=_strict_bool(
                adaptive_raw.get("enabled", False),
                "adaptive.enabled",
            ),
            bias_window=_strict_int(
                adaptive_raw.get("bias_window", 12),
                "adaptive.bias_window",
            ),
            max_abs_bias=float(adaptive_raw.get("max_abs_bias", 5.0)),
        ),
        actuator=ActuatorConfig(
            enabled=_strict_bool(
                actuator_raw.get("enabled", False),
                "actuator.enabled",
            ),
            url=_optional_string(actuator_raw.get("url"), "actuator.url"),
            bearer_token_env=_optional_string(
                actuator_raw.get("bearer_token_env"),
                "actuator.bearer_token_env",
            ),
            timeout_seconds=float(actuator_raw.get("timeout_seconds", 5.0)),
        ),
    )


DEFAULT_CONFIG_ENV = "MPC_CONFIG_PATH"


def load_controller_config(path: str | Path | None) -> ControllerConfig:
    config_source = path
    if config_source is None:
        config_source = os.environ.get(DEFAULT_CONFIG_ENV)
    if config_source is None:
        return ControllerConfig()
    config_path = Path(config_source)
    with config_path.open("r", encoding="utf-8-sig") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("config JSON root must be an object")
    return controller_config_from_mapping(payload)


def _mapping_or_empty(value: Any, field_name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _strict_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string or null")
    return value


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
