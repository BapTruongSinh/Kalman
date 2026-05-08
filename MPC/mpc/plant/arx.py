"""ARX artifact-backed plant model for MPC."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any, Sequence

from mpc.config import PumpLimits
from mpc.state import DisturbanceForecast, PlantRecord

_FIELD_TO_ATTR = {
    "Soil_Moisture": "soil_moisture",
    "Temperature": "temperature",
    "Humidity": "humidity",
    "Light": "light",
    "Drip": "drip",
    "Mist": "mist",
    "Fan": "fan",
}

_DEFAULT_INPUT_COLS = (
    "Temperature",
    "Humidity",
    "Light",
    "Drip",
    "Mist",
    "Fan",
)


@dataclass(frozen=True)
class ARXArtifactConfig:
    na: int
    nb: int
    nk: int
    include_intercept: bool
    input_cols: tuple[str, ...]
    output_col: str

    def __post_init__(self) -> None:
        if self.na < 1:
            raise ValueError("ARX na must be >= 1")
        if self.nb < 1:
            raise ValueError("ARX nb must be >= 1")
        if self.nk < 1:
            raise ValueError("ARX nk must be >= 1")
        if self.output_col not in _FIELD_TO_ATTR:
            raise ValueError(f"Unsupported output_col {self.output_col!r}")
        if not self.input_cols:
            raise ValueError("ARX input_cols must not be empty")
        unknown = [col for col in self.input_cols if col not in _FIELD_TO_ATTR]
        if unknown:
            raise ValueError(f"Unsupported ARX input column(s): {unknown}")

    @property
    def max_lag(self) -> int:
        return max(self.na, self.nb + self.nk - 1)

    @property
    def min_history_len(self) -> int:
        return self.max_lag

    def param_names(self) -> tuple[str, ...]:
        names: list[str] = [f"a{lag}" for lag in range(1, self.na + 1)]
        for col in self.input_cols:
            for lag in range(1, self.nb + 1):
                names.append(f"b_{col}_{lag}")
        if self.include_intercept:
            names.append("intercept")
        return tuple(names)


class ARXPlantModel:
    """Runtime plant adapter that reads `ARX/arx_model.json` only."""

    def __init__(
        self,
        *,
        config: ARXArtifactConfig,
        theta: Sequence[float],
        pump_limits: PumpLimits | None = None,
    ) -> None:
        self.config = config
        self.theta = tuple(float(v) for v in theta)
        self.pump_limits = pump_limits or PumpLimits()
        if len(self.theta) != len(self.config.param_names()):
            raise ValueError(
                "theta length does not match ARX config: "
                f"{len(self.theta)} != {len(self.config.param_names())}"
            )
        for value in self.theta:
            if not isfinite(value):
                raise ValueError("theta values must be finite")

    @property
    def min_history_len(self) -> int:
        return self.config.min_history_len

    @classmethod
    def load_artifact(
        cls,
        path: str | Path,
        *,
        pump_limits: PumpLimits | None = None,
        prefer_best_candidate: bool = True,
    ) -> "ARXPlantModel":
        artifact_path = Path(path)
        if not artifact_path.exists():
            raise FileNotFoundError(f"ARX artifact not found: {artifact_path}")
        with artifact_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("ARX artifact root must be an object")
        if data.get("model") != "ARX":
            raise ValueError("ARX artifact must contain model='ARX'")

        source: dict[str, Any] = data
        if prefer_best_candidate and isinstance(data.get("best_candidate"), dict):
            candidate = data["best_candidate"]
            if "theta_hat" in candidate:
                source = candidate

        cfg_raw = source.get("model_config") or data.get("model_config")
        theta_raw = source.get("theta_hat")
        if not isinstance(cfg_raw, dict):
            raise ValueError("ARX artifact missing model_config")
        if not isinstance(theta_raw, list):
            raise ValueError("ARX artifact missing theta_hat")

        config = ARXArtifactConfig(
            na=int(cfg_raw["na"]),
            nb=int(cfg_raw["nb"]),
            nk=int(cfg_raw["nk"]),
            include_intercept=bool(cfg_raw.get("include_intercept", False)),
            input_cols=tuple(cfg_raw.get("input_cols", _DEFAULT_INPUT_COLS)),
            output_col=str(cfg_raw.get("output_col", "Soil_Moisture")),
        )
        return cls(config=config, theta=theta_raw, pump_limits=pump_limits)

    def predict_next(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: float,
        step_seconds: int,
        disturbance: PlantRecord | None = None,
    ) -> float:
        if len(history) < self.min_history_len:
            raise ValueError(
                "history too short for ARX prediction: "
                f"{len(history)} < {self.min_history_len}"
            )
        latest = history[-1]
        base = latest if disturbance is None else disturbance
        duty = self.pump_limits.to_duty(pump_seconds, step_seconds)
        decision_record = PlantRecord(
            soil_moisture=latest.soil_moisture,
            temperature=base.temperature,
            humidity=base.humidity,
            light=base.light,
            drip=duty,
            mist=base.mist,
            fan=base.fan,
        )
        return self._predict_from_decision(history, decision_record)

    def forecast(
        self,
        history: Sequence[PlantRecord],
        *,
        pump_seconds: Sequence[float],
        step_seconds: int,
        disturbances: DisturbanceForecast,
    ) -> tuple[float, ...]:
        if len(pump_seconds) != disturbances.horizon_steps:
            raise ValueError("pump sequence and disturbance horizon must align")
        working_history = list(history)
        if len(working_history) < self.min_history_len:
            raise ValueError(
                "history too short for ARX forecast: "
                f"{len(working_history)} < {self.min_history_len}"
            )

        current_soil = working_history[-1].soil_moisture
        predictions: list[float] = []
        for index, pump in enumerate(pump_seconds):
            duty = self.pump_limits.to_duty(pump, step_seconds)
            decision_record = disturbances.record_at(
                index,
                soil_moisture=current_soil,
                drip=duty,
            )
            current_soil = self._predict_from_decision(
                working_history,
                decision_record,
            )
            predictions.append(current_soil)
            working_history.append(
                PlantRecord(
                    soil_moisture=current_soil,
                    temperature=decision_record.temperature,
                    humidity=decision_record.humidity,
                    light=decision_record.light,
                    drip=decision_record.drip,
                    mist=decision_record.mist,
                    fan=decision_record.fan,
                )
            )
        return tuple(predictions)

    def _predict_from_decision(
        self,
        history: Sequence[PlantRecord],
        decision_record: PlantRecord,
    ) -> float:
        if len(history) < self.min_history_len:
            raise ValueError(
                "history too short for ARX prediction: "
                f"{len(history)} < {self.min_history_len}"
            )
        row = self._build_prediction_row(history, decision_record)
        prediction = sum(coef * value for coef, value in zip(self.theta, row))
        if not isfinite(prediction):
            raise ValueError("ARX prediction is not finite")
        return prediction

    def _build_prediction_row(
        self,
        history: Sequence[PlantRecord],
        decision_record: PlantRecord,
    ) -> tuple[float, ...]:
        row: list[float] = []
        out_attr = _FIELD_TO_ATTR[self.config.output_col]
        for lag in range(1, self.config.na + 1):
            row.append(_get_record_value(history[-lag], out_attr))

        for col in self.config.input_cols:
            attr = _FIELD_TO_ATTR[col]
            for lag in range(self.config.nk, self.config.nk + self.config.nb):
                record = decision_record if lag == 1 else history[-(lag - 1)]
                row.append(_get_record_value(record, attr))

        if self.config.include_intercept:
            row.append(1.0)
        return tuple(row)


def _get_record_value(record: PlantRecord, attr: str) -> float:
    value = float(getattr(record, attr))
    if not isfinite(value):
        raise ValueError(f"record.{attr} must be finite")
    return value
