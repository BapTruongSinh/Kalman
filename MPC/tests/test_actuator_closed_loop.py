from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Sequence

from mpc.actuator import ActuatorCommand, ActuatorResult
from mpc.closed_loop import run_closed_loop
from mpc.config import ActuatorConfig, ControllerConfig, PumpLimits
from mpc.state import ControllerState, DisturbanceForecast, PlantRecord


class _PumpResponsiveModel:
    @property
    def min_history_len(self) -> int:
        return 1

    def predict_next(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: float,
        step_seconds: int,
        disturbance: PlantRecord | None = None,
    ) -> float:
        return history[-1].soil_moisture + (2.0 * pump_seconds / step_seconds)

    def forecast(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: Sequence[float],
        step_seconds: int,
        disturbances: DisturbanceForecast,
    ) -> tuple[float, ...]:
        current = history[-1].soil_moisture
        values: list[float] = []
        for pump in pump_seconds:
            current += 2.0 * pump / step_seconds
            values.append(current)
        return tuple(values)


class _CaptureHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        self.server.requests.append(  # type: ignore[attr-defined]
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "payload": json.loads(body.decode("utf-8")),
            }
        )
        self.send_response(self.server.response_code)  # type: ignore[attr-defined]
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: object) -> None:
        return


def test_closed_loop_posts_safe_command_to_fake_http_actuator(
    monkeypatch,
) -> None:
    with _fake_server() as server:
        monkeypatch.setenv("MPC_TEST_ACTUATOR_TOKEN", "secret-token")
        now = datetime(2026, 5, 9, 10, 0, tzinfo=timezone.utc)

        result = run_closed_loop(
            state=_state(now),
            history=_history(),
            plant_model=_PumpResponsiveModel(),
            config=_config(server.url),
            now=now,
            beam_width=4,
            command_id_factory=lambda: "cmd-1",
        )

        assert result.actuator.executed is True
        assert result.actuator.status == "sent"
        assert len(server.requests) == 1
        request = server.requests[0]
        assert request["authorization"] == "Bearer secret-token"
        assert request["payload"]["command_id"] == "cmd-1"
        assert request["payload"]["pump_seconds"] == 300.0
        assert request["payload"]["mode"] == "auto"
        assert request["payload"]["reason"] == "mpc_recommendation_safe"
        assert "secret-token" not in json.dumps(result.to_dict())


def test_closed_loop_stale_sample_posts_fail_closed_command(monkeypatch) -> None:
    with _fake_server() as server:
        monkeypatch.setenv("MPC_TEST_ACTUATOR_TOKEN", "secret-token")
        now = datetime(2026, 5, 9, 10, 0, tzinfo=timezone.utc)

        result = run_closed_loop(
            state=_state(now - timedelta(seconds=601)),
            history=_history(),
            plant_model=_PumpResponsiveModel(),
            config=_config(server.url),
            now=now,
            beam_width=4,
            command_id_factory=lambda: "cmd-stale",
        )

        assert result.recommendation.safety_status == "stale_sample"
        assert result.actuator.executed is True
        payload = server.requests[0]["payload"]
        assert payload["pump_seconds"] == 0.0
        assert payload["safety_status"] == "stale_sample"
        assert "stale_sample" in result.alerts


def test_closed_loop_missing_token_fails_closed_without_http(monkeypatch) -> None:
    with _fake_server() as server:
        monkeypatch.delenv("MPC_TEST_ACTUATOR_TOKEN", raising=False)
        now = datetime(2026, 5, 9, 10, 0, tzinfo=timezone.utc)

        result = run_closed_loop(
            state=_state(now),
            history=_history(),
            plant_model=_PumpResponsiveModel(),
            config=_config(server.url),
            now=now,
            beam_width=4,
            command_id_factory=lambda: "cmd-missing-token",
        )

        assert result.actuator.executed is False
        assert result.actuator.status == "config_error"
        assert result.actuator.command.pump_seconds == 0.0
        assert result.actuator.command.safety_status == "actuator_error"
        assert result.actuator.error == "actuator_token_missing"
        assert server.requests == []


def test_closed_loop_injected_client_still_requires_explicit_actuator_config() -> None:
    client = _FakeActuatorClient()
    now = datetime(2026, 5, 9, 10, 0, tzinfo=timezone.utc)

    result = run_closed_loop(
        state=_state(now),
        history=_history(),
        plant_model=_PumpResponsiveModel(),
        config=ControllerConfig(
            horizon_steps=1,
            pump=PumpLimits(max_seconds=300.0, grid_seconds=300.0),
        ),
        now=now,
        beam_width=4,
        actuator_client=client,
        command_id_factory=lambda: "cmd-bypass",
    )

    assert client.calls == []
    assert result.actuator.executed is False
    assert result.actuator.status == "config_error"
    assert result.actuator.command.pump_seconds == 0.0
    assert result.actuator.command.safety_status == "actuator_error"
    assert result.actuator.error == "actuator_disabled"
    assert "actuator_disabled" in result.alerts


def test_closed_loop_http_failure_returns_fail_closed_result(monkeypatch) -> None:
    with _fake_server(response_code=500) as server:
        monkeypatch.setenv("MPC_TEST_ACTUATOR_TOKEN", "secret-token")
        now = datetime(2026, 5, 9, 10, 0, tzinfo=timezone.utc)

        result = run_closed_loop(
            state=_state(now),
            history=_history(),
            plant_model=_PumpResponsiveModel(),
            config=_config(server.url),
            now=now,
            beam_width=4,
            command_id_factory=lambda: "cmd-http-fail",
        )

        assert len(server.requests) == 1
        assert result.actuator.executed is False
        assert result.actuator.status == "http_error"
        assert result.actuator.http_status_code == 500
        assert result.actuator.command.pump_seconds == 0.0
        assert result.actuator.command.safety_status == "actuator_error"
        assert "actuator_http_failure" in result.alerts


def _config(url: str) -> ControllerConfig:
    return ControllerConfig(
        horizon_steps=1,
        pump=PumpLimits(max_seconds=300.0, grid_seconds=300.0),
        actuator=ActuatorConfig(
            enabled=True,
            url=url,
            bearer_token_env="MPC_TEST_ACTUATOR_TOKEN",
            timeout_seconds=1.0,
        ),
    )


def _state(timestamp: datetime) -> ControllerState:
    return ControllerState(
        timestamp=timestamp,
        kf_x_posterior=54.0,
        temperature=27.0,
        humidity=72.0,
        light=300.0,
        last_pump_seconds=0.0,
        run_id=7,
    )


def _history() -> tuple[PlantRecord, ...]:
    return (
        PlantRecord(
            soil_moisture=54.0,
            temperature=27.0,
            humidity=72.0,
            light=300.0,
        ),
    )


class _FakeActuatorClient:
    def __init__(self) -> None:
        self.calls: list[ActuatorCommand] = []

    def send(self, command: ActuatorCommand) -> ActuatorResult:
        self.calls.append(command)
        return ActuatorResult(
            executed=True,
            status="sent",
            command=command,
            http_status_code=200,
        )


class _fake_server:
    def __init__(self, response_code: int = 200) -> None:
        self.response_code = response_code

    def __enter__(self):
        self.server = HTTPServer(("127.0.0.1", 0), _CaptureHandler)
        self.server.requests = []  # type: ignore[attr-defined]
        self.server.response_code = self.response_code  # type: ignore[attr-defined]
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{port}/actuator"
        self.requests = self.server.requests  # type: ignore[attr-defined]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)
