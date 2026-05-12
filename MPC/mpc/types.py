"""Public output contracts for MPC recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SafetyStatus = Literal[
    "safe",
    "pump_off_failsafe",
    "config_error",
    "stale_sample",
    "model_error",
    "solver_error",
    "actuator_error",
]


@dataclass(frozen=True)
class Recommendation:
    pump_seconds: float
    step_seconds: int
    predicted_soil_moisture: tuple[float, ...]
    target_band: dict[str, float]
    cost: float
    safety_status: SafetyStatus
    reason: str
    fao56: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "pump_seconds": self.pump_seconds,
            "step_seconds": self.step_seconds,
            "predicted_soil_moisture": list(self.predicted_soil_moisture),
            "target_band": dict(self.target_band),
            "cost": self.cost,
            "safety_status": self.safety_status,
            "reason": self.reason,
        }
        if self.fao56 is not None:
            payload["fao56"] = dict(self.fao56)
        return payload
