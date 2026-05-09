"""Live sensor validation for Adaptive Kalman ingestion."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .loader import RawRecord


@dataclass(frozen=True)
class ValidationConfig:
    """Physical bounds for live sensor payloads."""

    soil_moisture_min: float = 0.0
    soil_moisture_max: float = 100.0
    temperature_min: float = -10.0
    temperature_max: float = 60.0
    humidity_min: float = 0.0
    humidity_max: float = 100.0
    light_min: float = 0.0
    light_max: float = 150_000.0
    drip_min: float = 0.0
    drip_max: float = 1.0
    mist_min: float = 0.0
    mist_max: float = 1.0
    fan_min: float = 0.0
    fan_max: float = 1.0


DEFAULT_CONFIG = ValidationConfig()


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a live sensor sample."""

    is_valid: bool
    status: str
    reason: str = ""


_RANGE_CHECKS: tuple[tuple[str, str, str], ...] = (
    ("soil_moisture", "soil_moisture_min", "soil_moisture_max"),
    ("temperature", "temperature_min", "temperature_max"),
    ("humidity", "humidity_min", "humidity_max"),
    ("light", "light_min", "light_max"),
    ("drip", "drip_min", "drip_max"),
    ("mist", "mist_min", "mist_max"),
    ("fan", "fan_min", "fan_max"),
)


def validate_live_record(
    record: RawRecord,
    config: ValidationConfig = DEFAULT_CONFIG,
) -> ValidationResult:
    """Validate one live sensor sample.

    ``soil_moisture`` is the primary measurement. If it is absent, Kalman should
    execute a no-measurement step. Ancillary channels may be absent, but any
    channel that is present must be finite and inside its physical bounds.
    """
    if record.soil_moisture is None:
        return ValidationResult(
            is_valid=False,
            status="missing",
            reason="soil_moisture is absent; Kalman measurement-update step skipped",
        )

    out_of_range = []
    for attr, min_attr, max_attr in _RANGE_CHECKS:
        val = getattr(record, attr)
        if val is None:
            continue
        if not math.isfinite(val):
            out_of_range.append(f"{attr} is non-finite ({val!r})")
            continue
        lo = getattr(config, min_attr)
        hi = getattr(config, max_attr)
        if not (lo <= val <= hi):
            out_of_range.append(f"{attr}={val:.4g} not in [{lo}, {hi}]")

    if out_of_range:
        return ValidationResult(
            is_valid=False,
            status="out_of_range",
            reason="; ".join(out_of_range),
        )

    return ValidationResult(is_valid=True, status="valid")
