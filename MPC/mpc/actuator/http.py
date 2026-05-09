"""HTTP actuator adapter for the v3 closed-loop pilot."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from mpc.actuator.base import ActuatorCommand, ActuatorResult
from mpc.config import ActuatorConfig


@dataclass(frozen=True)
class HTTPActuatorClient:
    url: str
    bearer_token: str
    timeout_seconds: float

    @classmethod
    def from_config(cls, config: ActuatorConfig) -> "HTTPActuatorClient":
        if not config.enabled:
            raise ValueError("actuator_disabled")
        if config.url is None:
            raise ValueError("actuator_url_missing")
        if config.bearer_token_env is None:
            raise ValueError("actuator_token_env_missing")
        token = os.environ.get(config.bearer_token_env)
        if token is None or not token.strip():
            raise ValueError("actuator_token_missing")
        return cls(
            url=config.url,
            bearer_token=token,
            timeout_seconds=config.timeout_seconds,
        )

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("actuator_url_must_be_http_or_https")
        if not parsed.netloc:
            raise ValueError("actuator_url_missing_host")
        if not self.bearer_token:
            raise ValueError("actuator_token_missing")
        if self.timeout_seconds <= 0.0:
            raise ValueError("actuator_timeout_invalid")

    def send(self, command: ActuatorCommand) -> ActuatorResult:
        body = json.dumps(command.to_dict()).encode("utf-8")
        request = Request(
            self.url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status_code = int(response.status)
        except HTTPError as exc:
            return ActuatorResult(
                executed=False,
                status="http_error",
                command=command,
                http_status_code=exc.code,
                alert="actuator_http_failure",
                error=f"HTTP {exc.code}",
            )
        except (OSError, URLError) as exc:
            return ActuatorResult(
                executed=False,
                status="http_error",
                command=command,
                alert="actuator_http_failure",
                error=exc.__class__.__name__,
            )

        if not (200 <= status_code < 300):
            return ActuatorResult(
                executed=False,
                status="http_error",
                command=command,
                http_status_code=status_code,
                alert="actuator_http_failure",
                error=f"HTTP {status_code}",
            )
        return ActuatorResult(
            executed=True,
            status="sent",
            command=command,
            http_status_code=status_code,
        )
