"""JSON-serializable simulation report contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from mpc.config import ControllerConfig
from mpc.solver.cost import TrajectoryCost


@dataclass(frozen=True)
class SimulationMetrics:
    band_violation_steps: int
    band_violation_seconds: int
    band_violation_error_sum: float
    total_pump_seconds: float
    switching_count: int
    objective_cost: float
    cost_breakdown: dict[str, float]
    final_soil_moisture: float
    safety_counts: dict[str, int]
    mean_absolute_observation_error: float
    max_absolute_observation_error: float

    def to_dict(self) -> dict[str, object]:
        return {
            "band_violation_steps": self.band_violation_steps,
            "band_violation_seconds": self.band_violation_seconds,
            "band_violation_error_sum": self.band_violation_error_sum,
            "total_pump_seconds": self.total_pump_seconds,
            "switching_count": self.switching_count,
            "objective_cost": self.objective_cost,
            "cost_breakdown": dict(self.cost_breakdown),
            "final_soil_moisture": self.final_soil_moisture,
            "safety_counts": dict(self.safety_counts),
            "mean_absolute_observation_error": (
                self.mean_absolute_observation_error
            ),
            "max_absolute_observation_error": self.max_absolute_observation_error,
        }


@dataclass(frozen=True)
class SimulationReport:
    generated_at: datetime
    input_rows: int
    warmup_rows: int
    simulated_steps: int
    baseline_definition: dict[str, object]
    controllers: dict[str, SimulationMetrics]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "input_rows": self.input_rows,
            "warmup_rows": self.warmup_rows,
            "simulated_steps": self.simulated_steps,
            "baseline_definition": dict(self.baseline_definition),
            "controllers": {
                name: metrics.to_dict()
                for name, metrics in self.controllers.items()
            },
        }


def cost_breakdown(cost: TrajectoryCost) -> dict[str, float]:
    return {
        "band": cost.band,
        "overwater": cost.overwater,
        "terminal": cost.terminal,
        "water": cost.water,
        "switching": cost.switching,
        "daily_cap": cost.daily_cap,
    }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def config_summary(config: ControllerConfig) -> dict[str, object]:
    return {
        "step_seconds": config.step_seconds,
        "horizon_steps": config.horizon_steps,
        "target_band": {
            "low": config.target_band.low,
            "high": config.target_band.high,
        },
        "pump": {
            "min_seconds": config.pump.min_seconds,
            "max_seconds": config.pump.max_seconds,
            "grid_seconds": config.pump.grid_seconds,
        },
        "fao56": {
            "crop_kc": config.fao56.crop_kc,
            "soil_type": config.fao56.soil_type,
            "theta_fc": config.fao56.theta_fc,
            "theta_wp": config.fao56.theta_wp,
            "theta_sat": config.fao56.theta_sat,
            "root_depth_m": config.fao56.root_depth_m,
            "depletion_fraction_p": config.fao56.depletion_fraction_p,
            "et0_hour_mm": config.fao56.et0_hour_mm,
            "pump_efficiency": config.fao56.pump_efficiency,
            "pump_flow_lps": config.fao56.pump_flow_lps,
            "irrigation_area_m2": config.fao56.irrigation_area_m2,
        },
        "adaptive": {
            "enabled": config.adaptive.enabled,
            "bias_window": config.adaptive.bias_window,
            "max_abs_bias": config.adaptive.max_abs_bias,
        },
        "actuator": {
            "enabled": config.actuator.enabled,
            "url_configured": config.actuator.url is not None,
            "bearer_token_env_configured": (
                config.actuator.bearer_token_env is not None
            ),
            "timeout_seconds": config.actuator.timeout_seconds,
        },
    }
