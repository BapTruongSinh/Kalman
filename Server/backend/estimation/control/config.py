"""Map persisted greenhouse control profiles to MPC runtime config."""

from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse

from mpc.config import (
    ActuatorConfig,
    AdaptiveConfig,
    ControllerConfig,
    CostWeights,
    PumpLimits,
    SafetyConfig,
    TargetBand,
)

from estimation.models import GreenhouseControlProfile

_LOCAL_HOSTS = {"localhost", "localhost.localdomain"}


def profile_to_controller_config(
    profile: GreenhouseControlProfile,
) -> ControllerConfig:
    """Build an MPC ControllerConfig from a DB profile.

    The API never accepts model paths or raw actuator tokens. Actuator URL/token
    env names can only come from the persisted operator-controlled profile.
    """

    actuator_url = (profile.actuator_url or "").strip() or None
    if profile.actuator_enabled and actuator_url is not None:
        validate_actuator_url(actuator_url)

    return ControllerConfig(
        step_seconds=int(profile.step_seconds),
        horizon_steps=int(profile.horizon_steps),
        target_band=TargetBand(
            low=float(profile.target_low),
            high=float(profile.target_high),
        ),
        pump=PumpLimits(
            min_seconds=float(profile.pump_min_seconds),
            max_seconds=float(profile.pump_max_seconds),
            grid_seconds=float(profile.pump_grid_seconds),
        ),
        cost=CostWeights(
            band_violation=float(profile.cost_band_violation),
            terminal_band_violation=float(profile.cost_terminal_band_violation),
            water_use=float(profile.cost_water_use),
            switching=float(profile.cost_switching),
            daily_cap_excess=float(profile.cost_daily_cap_excess),
        ),
        safety=SafetyConfig(
            stale_after_seconds=int(profile.safety_stale_after_seconds),
            soft_daily_pump_cap_seconds=float(profile.soft_daily_pump_cap_seconds),
        ),
        adaptive=AdaptiveConfig(
            enabled=bool(profile.adaptive_enabled),
            bias_window=int(profile.adaptive_bias_window),
            max_abs_bias=float(profile.adaptive_max_abs_bias),
        ),
        actuator=ActuatorConfig(
            enabled=bool(profile.actuator_enabled),
            url=actuator_url,
            bearer_token_env=(
                (profile.actuator_bearer_token_env or "").strip() or None
            ),
            timeout_seconds=float(profile.actuator_timeout_seconds),
        ),
    )


def profile_snapshot(profile: GreenhouseControlProfile) -> dict[str, object]:
    """Return a JSON-safe config snapshot without leaking token/env details."""

    return {
        "profile_id": profile.pk,
        "greenhouse_id": profile.greenhouse_id,
        "crop_name": profile.crop_name,
        "crop_kc": profile.crop_kc,
        "target_band": {
            "low": profile.target_low,
            "high": profile.target_high,
        },
        "pump": {
            "min_seconds": profile.pump_min_seconds,
            "max_seconds": profile.pump_max_seconds,
            "grid_seconds": profile.pump_grid_seconds,
        },
        "step_seconds": profile.step_seconds,
        "horizon_steps": profile.horizon_steps,
        "cost": {
            "band_violation": profile.cost_band_violation,
            "water_use": profile.cost_water_use,
            "switching": profile.cost_switching,
            "daily_cap_excess": profile.cost_daily_cap_excess,
            "terminal_band_violation": profile.cost_terminal_band_violation,
        },
        "adaptive": {
            "enabled": profile.adaptive_enabled,
            "bias_window": profile.adaptive_bias_window,
            "max_abs_bias": profile.adaptive_max_abs_bias,
        },
        "safety": {
            "stale_after_seconds": profile.safety_stale_after_seconds,
            "soft_daily_pump_cap_seconds": profile.soft_daily_pump_cap_seconds,
        },
        "actuator": {
            "enabled": profile.actuator_enabled,
            "url_configured": bool(profile.actuator_url),
            "bearer_token_env_configured": bool(profile.actuator_bearer_token_env),
            "timeout_seconds": profile.actuator_timeout_seconds,
        },
    }


def validate_actuator_url(url: str) -> None:
    """Reject obviously unsafe actuator URLs before HTTP client construction."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("actuator_url_must_be_http_or_https")
    if not parsed.hostname:
        raise ValueError("actuator_url_missing_host")

    host = parsed.hostname.strip().lower()
    if host in _LOCAL_HOSTS or host.endswith(".local"):
        raise ValueError("actuator_url_host_not_allowed")

    try:
        addr = ip_address(host)
    except ValueError:
        return

    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        raise ValueError("actuator_url_host_not_allowed")
