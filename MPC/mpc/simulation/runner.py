"""Offline v2 simulation runner for MPC and threshold baseline comparison."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Iterable, Sequence

from mpc.config import ControllerConfig
from mpc.plant import PlantModel
from mpc.simulation.baseline import baseline_definition, threshold_baseline_pump_seconds
from mpc.simulation.report import (
    SimulationMetrics,
    SimulationReport,
    cost_breakdown,
    utc_now,
)
from mpc.solver.cost import TrajectoryCost, band_error
from mpc.solver.grid import GridShootingSolver
from mpc.state import ControllerState, DisturbanceForecast, PlantRecord

_REQUIRED_COLUMNS = {
    "Timestamp",
    "Soil_Moisture",
    "Temperature",
    "Humidity",
    "Light",
}


@dataclass(frozen=True)
class SimulationRow:
    timestamp: datetime
    soil_moisture: float
    temperature: float
    humidity: float
    light: float
    drip: float = 0.0
    mist: float = 0.0
    fan: float = 0.0

    def to_plant_record(self) -> PlantRecord:
        return PlantRecord(
            soil_moisture=self.soil_moisture,
            temperature=self.temperature,
            humidity=self.humidity,
            light=self.light,
            drip=self.drip,
            mist=self.mist,
            fan=self.fan,
        )


@dataclass(frozen=True)
class _RolloutResult:
    soils: tuple[float, ...]
    pumps: tuple[float, ...]
    dates: tuple[date, ...]
    safety_counts: dict[str, int]


def run_simulation(
    *,
    csv_path: str | Path,
    plant_model: PlantModel,
    config: ControllerConfig,
    max_steps: int | None = None,
    beam_width: int = 32,
) -> SimulationReport:
    rows = read_simulation_csv(csv_path)
    warmup_rows = plant_model.min_history_len
    if len(rows) <= warmup_rows:
        raise ValueError(
            "CSV input must contain more rows than plant min_history_len"
        )
    if max_steps is not None and max_steps < 1:
        raise ValueError("max_steps must be >= 1")

    candidate_rows = rows[warmup_rows:]
    if max_steps is not None:
        candidate_rows = candidate_rows[:max_steps]
    if not candidate_rows:
        raise ValueError("simulation has no rows after warmup")

    initial_history = [row.to_plant_record() for row in rows[:warmup_rows]]
    initial_soil = initial_history[-1].soil_moisture
    initial_pump = config.pump.to_duty(
        initial_history[-1].drip * config.step_seconds,
        config.step_seconds,
    ) * config.step_seconds

    mpc_result = _rollout_mpc(
        rows=candidate_rows,
        initial_soil=initial_soil,
        initial_pump=initial_pump,
        initial_history=initial_history,
        plant_model=plant_model,
        config=config,
        beam_width=beam_width,
    )
    threshold_result = _rollout_threshold(
        rows=candidate_rows,
        initial_soil=initial_soil,
        initial_pump=initial_pump,
        initial_history=initial_history,
        plant_model=plant_model,
        config=config,
    )

    return SimulationReport(
        generated_at=utc_now(),
        input_rows=len(rows),
        warmup_rows=warmup_rows,
        simulated_steps=len(candidate_rows),
        baseline_definition=baseline_definition(config),
        controllers={
            "mpc": _metrics(
                result=mpc_result,
                previous_pump_seconds=initial_pump,
                config=config,
            ),
            "threshold": _metrics(
                result=threshold_result,
                previous_pump_seconds=initial_pump,
                config=config,
            ),
        },
    )


def read_simulation_csv(path: str | Path) -> tuple[SimulationRow, ...]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV input not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV input has no header")
        missing = sorted(_REQUIRED_COLUMNS - set(reader.fieldnames))
        if missing:
            raise ValueError(f"CSV input missing columns: {missing}")
        rows = tuple(_row_from_mapping(row) for row in reader)
    if not rows:
        raise ValueError("CSV input has no data rows")
    return rows


def _rollout_mpc(
    *,
    rows: Sequence[SimulationRow],
    initial_soil: float,
    initial_pump: float,
    initial_history: Sequence[PlantRecord],
    plant_model: PlantModel,
    config: ControllerConfig,
    beam_width: int,
) -> _RolloutResult:
    solver = GridShootingSolver(config, beam_width=beam_width)
    current_soil = initial_soil
    previous_pump = initial_pump
    history = list(initial_history)
    soils: list[float] = []
    pumps: list[float] = []
    dates: list[date] = []
    safety_counts: dict[str, int] = {}
    daily_usage: dict[datetime.date, float] = {}

    for row in rows:
        used_today = daily_usage.get(row.timestamp.date(), 0.0)
        state = ControllerState(
            timestamp=row.timestamp,
            kf_x_posterior=current_soil,
            temperature=row.temperature,
            humidity=row.humidity,
            light=row.light,
            last_pump_seconds=previous_pump,
        )
        recommendation = solver.recommend(
            state=state,
            history=history,
            plant_model=plant_model,
            now=row.timestamp,
            used_today_pump_seconds=used_today,
        )
        pump = recommendation.pump_seconds
        safety_counts[recommendation.safety_status] = (
            safety_counts.get(recommendation.safety_status, 0) + 1
        )
        current_soil = _predict_next(
            current_soil=current_soil,
            row=row,
            pump_seconds=pump,
            history=history,
            plant_model=plant_model,
            config=config,
        )
        history.append(
            PlantRecord(
                soil_moisture=current_soil,
                temperature=row.temperature,
                humidity=row.humidity,
                light=row.light,
                drip=config.pump.to_duty(pump, config.step_seconds),
                mist=row.mist,
                fan=row.fan,
            )
        )
        soils.append(current_soil)
        pumps.append(pump)
        dates.append(row.timestamp.date())
        daily_usage[row.timestamp.date()] = used_today + pump
        previous_pump = pump

    return _RolloutResult(
        soils=tuple(soils),
        pumps=tuple(pumps),
        dates=tuple(dates),
        safety_counts=safety_counts,
    )


def _rollout_threshold(
    *,
    rows: Sequence[SimulationRow],
    initial_soil: float,
    initial_pump: float,
    initial_history: Sequence[PlantRecord],
    plant_model: PlantModel,
    config: ControllerConfig,
) -> _RolloutResult:
    current_soil = initial_soil
    previous_pump = initial_pump
    history = list(initial_history)
    soils: list[float] = []
    pumps: list[float] = []
    dates: list[date] = []

    for row in rows:
        pump = threshold_baseline_pump_seconds(current_soil, config)
        current_soil = _predict_next(
            current_soil=current_soil,
            row=row,
            pump_seconds=pump,
            history=history,
            plant_model=plant_model,
            config=config,
        )
        history.append(
            PlantRecord(
                soil_moisture=current_soil,
                temperature=row.temperature,
                humidity=row.humidity,
                light=row.light,
                drip=config.pump.to_duty(pump, config.step_seconds),
                mist=row.mist,
                fan=row.fan,
            )
        )
        soils.append(current_soil)
        pumps.append(pump)
        dates.append(row.timestamp.date())
        previous_pump = pump

    return _RolloutResult(
        soils=tuple(soils),
        pumps=tuple(pumps),
        dates=tuple(dates),
        safety_counts={"not_applicable": len(pumps)},
    )


def _predict_next(
    *,
    current_soil: float,
    row: SimulationRow,
    pump_seconds: float,
    history: Sequence[PlantRecord],
    plant_model: PlantModel,
    config: ControllerConfig,
) -> float:
    disturbance = PlantRecord(
        soil_moisture=current_soil,
        temperature=row.temperature,
        humidity=row.humidity,
        light=row.light,
        drip=config.pump.to_duty(pump_seconds, config.step_seconds),
        mist=row.mist,
        fan=row.fan,
    )
    prediction = plant_model.predict_next(
        history,
        pump_seconds=pump_seconds,
        step_seconds=config.step_seconds,
        disturbance=disturbance,
    )
    if not isfinite(prediction):
        raise ValueError("plant prediction must be finite")
    return prediction


def _metrics(
    *,
    result: _RolloutResult,
    previous_pump_seconds: float,
    config: ControllerConfig,
) -> SimulationMetrics:
    violation_errors = [
        band_error(
            value,
            low=config.target_band.low,
            high=config.target_band.high,
        )
        for value in result.soils
    ]
    cost = _score_with_daily_reset(
        predictions=result.soils,
        pump_seconds=result.pumps,
        dates=result.dates,
        previous_pump_seconds=previous_pump_seconds,
        config=config,
    )
    return SimulationMetrics(
        band_violation_steps=sum(1 for error in violation_errors if error > 0.0),
        band_violation_seconds=sum(
            config.step_seconds for error in violation_errors if error > 0.0
        ),
        band_violation_error_sum=sum(violation_errors),
        total_pump_seconds=sum(result.pumps),
        switching_count=_switching_count(
            result.pumps,
            previous_pump_seconds=previous_pump_seconds,
        ),
        objective_cost=cost.total,
        cost_breakdown=cost_breakdown(cost),
        final_soil_moisture=result.soils[-1],
        safety_counts=result.safety_counts,
    )


def _switching_count(
    pumps: Iterable[float],
    *,
    previous_pump_seconds: float,
) -> int:
    count = 0
    previous = previous_pump_seconds
    for pump in pumps:
        if abs(pump - previous) > 1e-9:
            count += 1
        previous = pump
    return count


def _score_with_daily_reset(
    *,
    predictions: Sequence[float],
    pump_seconds: Sequence[float],
    dates: Sequence[date],
    previous_pump_seconds: float,
    config: ControllerConfig,
) -> TrajectoryCost:
    if not (len(predictions) == len(pump_seconds) == len(dates)):
        raise ValueError("predictions, pump sequence, and dates must align")
    if not predictions:
        raise ValueError("trajectory must not be empty")
    if not isfinite(previous_pump_seconds):
        raise ValueError("previous_pump_seconds must be finite")

    band_total = 0.0
    water_total = 0.0
    switching_total = 0.0
    daily_cap_total = 0.0
    previous_pump = previous_pump_seconds
    daily_usage: dict[date, float] = {}

    for value, pump, day in zip(predictions, pump_seconds, dates):
        if not isfinite(value):
            raise ValueError("predicted soil moisture must be finite")
        if not isfinite(pump):
            raise ValueError("pump_seconds must be finite")
        if pump < 0.0:
            raise ValueError("pump_seconds must be >= 0")

        error = band_error(
            value,
            low=config.target_band.low,
            high=config.target_band.high,
        )
        pump_ratio = pump / float(config.step_seconds)
        switch_ratio = abs(pump - previous_pump) / float(config.step_seconds)
        cumulative_today = daily_usage.get(day, 0.0) + pump
        daily_usage[day] = cumulative_today
        daily_excess_ratio = max(
            0.0,
            cumulative_today - config.safety.soft_daily_pump_cap_seconds,
        ) / float(config.step_seconds)

        band_total += config.cost.band_violation * error * error
        water_total += config.cost.water_use * pump_ratio * pump_ratio
        switching_total += config.cost.switching * switch_ratio * switch_ratio
        daily_cap_total += (
            config.cost.daily_cap_excess
            * daily_excess_ratio
            * daily_excess_ratio
        )
        previous_pump = pump

    terminal_error = band_error(
        predictions[-1],
        low=config.target_band.low,
        high=config.target_band.high,
    )
    terminal_total = (
        config.cost.terminal_band_violation
        * terminal_error
        * terminal_error
    )
    total = (
        band_total
        + water_total
        + switching_total
        + daily_cap_total
        + terminal_total
    )
    return TrajectoryCost(
        total=total,
        band=band_total,
        terminal=terminal_total,
        water=water_total,
        switching=switching_total,
        daily_cap=daily_cap_total,
    )


def _row_from_mapping(row: dict[str, str]) -> SimulationRow:
    return SimulationRow(
        timestamp=_parse_timestamp(row["Timestamp"]),
        soil_moisture=_required_float(row, "Soil_Moisture"),
        temperature=_required_float(row, "Temperature"),
        humidity=_required_float(row, "Humidity"),
        light=_required_float(row, "Light"),
        drip=_optional_float(row, "Drip"),
        mist=_optional_float(row, "Mist"),
        fan=_optional_float(row, "Fan"),
    )


def _parse_timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp


def _required_float(row: dict[str, str], column: str) -> float:
    value = float(row[column])
    if not isfinite(value):
        raise ValueError(f"{column} must be finite")
    return value


def _optional_float(row: dict[str, str], column: str) -> float:
    raw = row.get(column, "")
    if raw == "":
        return 0.0
    value = float(raw)
    if not isfinite(value):
        raise ValueError(f"{column} must be finite")
    return value
