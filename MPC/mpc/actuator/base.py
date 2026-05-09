"""Actuator command value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from mpc.types import SafetyStatus


@dataclass(frozen=True)
class ActuatorCommand:
    command_id: str
    timestamp: datetime
    run_id: int | None
    pump_seconds: float
    step_seconds: int
    mode: str
    reason: str
    safety_status: SafetyStatus

    def __post_init__(self) -> None:
        if not self.command_id:
            raise ValueError("command_id must not be empty")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        if self.run_id is not None and (
            isinstance(self.run_id, bool) or not isinstance(self.run_id, int)
        ):
            raise ValueError("run_id must be an int or null")
        if not isfinite(self.pump_seconds) or self.pump_seconds < 0.0:
            raise ValueError("pump_seconds must be finite and >= 0")
        if self.step_seconds <= 0:
            raise ValueError("step_seconds must be > 0")
        if self.mode != "auto":
            raise ValueError("actuator command mode must be auto")
        if not self.reason:
            raise ValueError("reason must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "command_id": self.command_id,
            "timestamp": self.timestamp.isoformat(),
            "run_id": self.run_id,
            "pump_seconds": self.pump_seconds,
            "step_seconds": self.step_seconds,
            "mode": self.mode,
            "reason": self.reason,
            "safety_status": self.safety_status,
        }


@dataclass(frozen=True)
class ActuatorResult:
    executed: bool
    status: str
    command: ActuatorCommand
    http_status_code: int | None = None
    alert: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "executed": self.executed,
            "status": self.status,
            "command": self.command.to_dict(),
            "http_status_code": self.http_status_code,
            "alert": self.alert,
            "error": self.error,
        }
