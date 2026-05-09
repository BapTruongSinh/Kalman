"""Runtime defaults and config schema export for MPC/AMPC clients."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mpc.config import ControllerConfig

DEFAULT_RUNTIME_PATHS: dict[str, str | None] = {
    "artifact": "../ARX/arx_model.json",
    "state_json": "examples/demo_state.json",
    "history_json": None,
    "simulation_input": "../ARX/greenhouse_data.csv",
    "recommend_output": "reports/recommendation.json",
    "simulate_output": "reports/v2_simulation.json",
    "adaptive_simulate_output": "reports/v3_adaptive_simulation.json",
    "closed_loop_output": "reports/closed_loop_dry_run.json",
    "config": None,
}

DEFAULT_RUNTIME_VALUES: dict[str, int | float | None] = {
    "beam_width": 32,
    "max_steps": None,
    "used_today_pump_seconds": 0.0,
}


def controller_config_to_dict(config: ControllerConfig) -> dict[str, Any]:
    """Return a JSON-serializable controller config payload."""

    return asdict(config)


def default_config_schema() -> dict[str, Any]:
    """Return defaults and field grouping for UI/API clients."""

    return {
        "schema_version": 1,
        "controller_defaults": controller_config_to_dict(ControllerConfig()),
        "runtime_defaults": {
            **DEFAULT_RUNTIME_PATHS,
            **DEFAULT_RUNTIME_VALUES,
        },
        "field_groups": {
            "user_inputs": [
                _field(
                    "target_band.low",
                    "number",
                    "Lower soil moisture bound for the crop.",
                ),
                _field(
                    "target_band.high",
                    "number",
                    "Upper soil moisture bound for the crop.",
                ),
                _field(
                    "pump.max_seconds",
                    "number",
                    "Maximum pump seconds in one control step.",
                ),
                _field(
                    "safety.soft_daily_pump_cap_seconds",
                    "number",
                    "Soft cap for total pump seconds per day.",
                ),
                _field(
                    "crop.kc",
                    "number",
                    "Crop coefficient for future website/ET logic; MPC runtime does not use it yet.",
                    runtime_field=False,
                ),
                _field(
                    "actuator.enabled",
                    "boolean",
                    "Allow sending commands to the HTTP actuator.",
                ),
                _field(
                    "actuator.url",
                    "string|null",
                    "HTTP actuator endpoint, configured outside code.",
                    secret=False,
                ),
                _field(
                    "actuator.bearer_token_env",
                    "string|null",
                    "Environment variable name that stores the Bearer token, not the token value.",
                    secret=False,
                ),
            ],
            "system_defaults": [
                _field(
                    "artifact",
                    "path",
                    "Default ARX artifact path.",
                ),
                _field(
                    "state_json",
                    "path",
                    "Default demo state JSON; live runtime can replace this with a real state source.",
                ),
                _field(
                    "simulation_input",
                    "path",
                    "Default CSV trace for simulation.",
                ),
                _field(
                    "step_seconds",
                    "integer",
                    "Control step duration in seconds.",
                ),
                _field(
                    "horizon_steps",
                    "integer",
                    "Number of forecast steps in the horizon.",
                ),
                _field(
                    "pump.min_seconds",
                    "number",
                    "Lower bound for pump command.",
                ),
                _field(
                    "pump.grid_seconds",
                    "number",
                    "Grid-search resolution for candidate pump commands.",
                ),
                _field(
                    "cost.band_violation",
                    "number",
                    "Weight for target-band error.",
                ),
                _field(
                    "cost.water_use",
                    "number",
                    "Weight for water use.",
                ),
                _field(
                    "cost.switching",
                    "number",
                    "Weight for changing pump command.",
                ),
                _field(
                    "cost.daily_cap_excess",
                    "number",
                    "Weight for exceeding the soft daily cap.",
                ),
                _field(
                    "cost.terminal_band_violation",
                    "number",
                    "Weight for final horizon state outside the band.",
                ),
                _field(
                    "adaptive.bias_window",
                    "integer",
                    "Number of residuals used for moving-average bias.",
                ),
                _field(
                    "adaptive.max_abs_bias",
                    "number",
                    "Absolute bound for bias correction.",
                ),
                _field(
                    "beam_width",
                    "integer",
                    "Candidate sequences retained per step in the beam-grid solver.",
                ),
            ],
        },
    }


def _field(
    name: str,
    value_type: str,
    description: str,
    *,
    runtime_field: bool = True,
    secret: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "type": value_type,
        "description": description,
        "runtime_field": runtime_field,
        "secret": secret,
    }
