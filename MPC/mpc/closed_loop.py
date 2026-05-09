"""Closed-loop controller service for the v3 HTTP actuator pilot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol, Sequence
from uuid import uuid4

from mpc.actuator import ActuatorCommand, ActuatorResult, HTTPActuatorClient
from mpc.config import ControllerConfig
from mpc.plant import PlantModel
from mpc.solver import GridShootingSolver
from mpc.state import ControllerState, PlantRecord
from mpc.types import Recommendation


class ActuatorClient(Protocol):
    def send(self, command: ActuatorCommand) -> ActuatorResult:
        ...


@dataclass(frozen=True)
class ClosedLoopResult:
    recommendation: Recommendation
    actuator: ActuatorResult
    alerts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "recommendation": self.recommendation.to_dict(),
            "actuator": self.actuator.to_dict(),
            "alerts": list(self.alerts),
        }


def run_closed_loop(
    *,
    state: ControllerState,
    history: Sequence[PlantRecord],
    plant_model: PlantModel,
    config: ControllerConfig,
    now: datetime | None = None,
    used_today_pump_seconds: float = 0.0,
    beam_width: int = 32,
    actuator_client: ActuatorClient | None = None,
    command_id_factory: Callable[[], str] | None = None,
) -> ClosedLoopResult:
    recommendation = GridShootingSolver(
        config,
        beam_width=beam_width,
    ).recommend(
        state=state,
        history=history,
        plant_model=plant_model,
        now=now,
        used_today_pump_seconds=used_today_pump_seconds,
    )
    command = _command_from_recommendation(
        state=state,
        recommendation=recommendation,
        config=config,
        now=now,
        command_id_factory=command_id_factory,
    )
    alerts = _alerts_for_recommendation(recommendation)

    try:
        configured_client = HTTPActuatorClient.from_config(config.actuator)
        client = actuator_client if actuator_client is not None else configured_client
    except ValueError as exc:
        fail_command = _fail_closed_command(
            state=state,
            config=config,
            now=now,
            reason=str(exc),
            command_id_factory=command_id_factory,
        )
        actuator_result = ActuatorResult(
            executed=False,
            status="config_error",
            command=fail_command,
            alert=str(exc),
            error=str(exc),
        )
        return ClosedLoopResult(
            recommendation=recommendation,
            actuator=actuator_result,
            alerts=alerts + (str(exc),),
        )

    result = client.send(command)
    if result.executed:
        return ClosedLoopResult(
            recommendation=recommendation,
            actuator=result,
            alerts=alerts,
        )

    fail_command = _fail_closed_command(
        state=state,
        config=config,
        now=now,
        reason=result.alert or result.status,
        command_id_factory=command_id_factory,
    )
    return ClosedLoopResult(
        recommendation=recommendation,
        actuator=ActuatorResult(
            executed=False,
            status=result.status,
            command=fail_command,
            http_status_code=result.http_status_code,
            alert=result.alert,
            error=result.error,
        ),
        alerts=alerts + tuple(
            value
            for value in (result.alert, result.error)
            if value is not None
        ),
    )


def _command_from_recommendation(
    *,
    state: ControllerState,
    recommendation: Recommendation,
    config: ControllerConfig,
    now: datetime | None,
    command_id_factory: Callable[[], str] | None,
) -> ActuatorCommand:
    pump_seconds = (
        recommendation.pump_seconds
        if recommendation.safety_status == "safe"
        else config.safety.fail_closed_pump_seconds
    )
    reason = (
        "mpc_recommendation_safe"
        if recommendation.safety_status == "safe"
        else recommendation.reason
    )
    return ActuatorCommand(
        command_id=_command_id(command_id_factory),
        timestamp=_command_time(now),
        run_id=state.run_id,
        pump_seconds=config.pump.clamp(pump_seconds),
        step_seconds=config.step_seconds,
        mode="auto",
        reason=reason,
        safety_status=recommendation.safety_status,
    )


def _fail_closed_command(
    *,
    state: ControllerState,
    config: ControllerConfig,
    now: datetime | None,
    reason: str,
    command_id_factory: Callable[[], str] | None,
) -> ActuatorCommand:
    return ActuatorCommand(
        command_id=_command_id(command_id_factory),
        timestamp=_command_time(now),
        run_id=state.run_id,
        pump_seconds=config.safety.fail_closed_pump_seconds,
        step_seconds=config.step_seconds,
        mode="auto",
        reason=reason,
        safety_status="actuator_error",
    )


def _alerts_for_recommendation(
    recommendation: Recommendation,
) -> tuple[str, ...]:
    if recommendation.safety_status == "safe":
        return ()
    return (recommendation.reason,)


def _command_time(now: datetime | None) -> datetime:
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp


def _command_id(factory: Callable[[], str] | None) -> str:
    if factory is None:
        return str(uuid4())
    command_id = factory()
    if not command_id:
        raise ValueError("command_id must not be empty")
    return command_id
