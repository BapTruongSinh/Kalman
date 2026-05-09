"""Command line entry point for standalone MPC workflows."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from mpc.closed_loop import run_closed_loop
from mpc.config import ControllerConfig, load_controller_config
from mpc.plant import ARXPlantModel
from mpc.schema import DEFAULT_RUNTIME_PATHS, default_config_schema
from mpc.simulation import run_adaptive_simulation, run_simulation
from mpc.simulation.report import config_summary
from mpc.solver import GridShootingSolver
from mpc.state import ControllerState, PlantRecord


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "recommend":
            _run_recommend(args)
        elif args.command == "simulate":
            _run_simulate(args)
        elif args.command == "adaptive-simulate":
            _run_adaptive_simulate(args)
        elif args.command == "closed-loop":
            _run_closed_loop(args)
        elif args.command == "auto":
            _run_closed_loop(args)
        elif args.command == "config-schema":
            _run_config_schema(args)
        else:
            parser.error("unknown command")
    except Exception as exc:  # noqa: BLE001
        print(f"mpc: error: {exc}", file=sys.stderr)
        return 2
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mpc",
        description="Standalone MPC/AMPC controller CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    recommend = subparsers.add_parser(
        "recommend",
        help="write one v2 pump recommendation JSON",
    )
    recommend.add_argument("--artifact", default=None)
    recommend.add_argument("--state-json", default=None)
    recommend.add_argument("--output", default=None)
    recommend.add_argument("--config", default=None)
    recommend.add_argument("--history-json", default=None)
    recommend.add_argument("--now", default=None)
    recommend.add_argument("--used-today-pump-seconds", type=float, default=0.0)
    recommend.add_argument("--beam-width", type=int, default=32)

    simulate = subparsers.add_parser(
        "simulate",
        help="compare v2 MPC against threshold baseline over CSV input",
    )
    simulate.add_argument("--artifact", default=None)
    simulate.add_argument("--input", default=None)
    simulate.add_argument("--output", default=None)
    simulate.add_argument("--config", default=None)
    simulate.add_argument("--max-steps", type=int, default=None)
    simulate.add_argument("--beam-width", type=int, default=32)

    adaptive_simulate = subparsers.add_parser(
        "adaptive-simulate",
        help="compare v2 MPC, v3 AMPC, and threshold baseline over CSV input",
    )
    adaptive_simulate.add_argument("--artifact", default=None)
    adaptive_simulate.add_argument("--input", default=None)
    adaptive_simulate.add_argument("--output", default=None)
    adaptive_simulate.add_argument("--config", default=None)
    adaptive_simulate.add_argument("--max-steps", type=int, default=None)
    adaptive_simulate.add_argument("--beam-width", type=int, default=32)

    closed_loop = subparsers.add_parser(
        "closed-loop",
        help="run one v3 closed-loop recommendation and optional HTTP actuator POST",
    )
    closed_loop.add_argument("--artifact", default=None)
    closed_loop.add_argument("--state-json", default=None)
    closed_loop.add_argument("--output", default=None)
    closed_loop.add_argument("--config", default=None)
    closed_loop.add_argument("--history-json", default=None)
    closed_loop.add_argument("--now", default=None)
    closed_loop.add_argument("--used-today-pump-seconds", type=float, default=0.0)
    closed_loop.add_argument("--beam-width", type=int, default=32)

    auto = subparsers.add_parser(
        "auto",
        help="run one v3 auto control step; alias for closed-loop",
    )
    auto.add_argument("--artifact", default=None)
    auto.add_argument("--state-json", default=None)
    auto.add_argument("--output", default=None)
    auto.add_argument("--config", default=None)
    auto.add_argument("--history-json", default=None)
    auto.add_argument("--now", default=None)
    auto.add_argument("--used-today-pump-seconds", type=float, default=0.0)
    auto.add_argument("--beam-width", type=int, default=32)

    config_schema = subparsers.add_parser(
        "config-schema",
        help="write website-loadable controller defaults and field groups",
    )
    config_schema.add_argument("--output", default=None)
    return parser


def _run_recommend(args: argparse.Namespace) -> None:
    config = load_controller_config(args.config)
    plant_model = ARXPlantModel.load_artifact(
        _input_path(args.artifact, "artifact"),
        pump_limits=config.pump,
    )
    state_payload = _read_json_object(
        _input_path(args.state_json, "state_json"),
        "state JSON",
    )
    state = ControllerState.from_mapping(state_payload)
    history = (
        _read_history_json(args.history_json)
        if args.history_json is not None
        else _default_history(state, plant_model.min_history_len, config)
    )
    now = _parse_optional_datetime(args.now)
    if now is None and args.state_json is None:
        now = state.timestamp
    recommendation = GridShootingSolver(
        config,
        beam_width=args.beam_width,
    ).recommend(
        state=state,
        history=history,
        plant_model=plant_model,
        now=now,
        used_today_pump_seconds=args.used_today_pump_seconds,
    )
    _write_json(
        _output_path(args.output, "recommend_output"),
        recommendation.to_dict(),
    )


def _run_simulate(args: argparse.Namespace) -> None:
    config = load_controller_config(args.config)
    plant_model = ARXPlantModel.load_artifact(
        _input_path(args.artifact, "artifact"),
        pump_limits=config.pump,
    )
    report = run_simulation(
        csv_path=_input_path(args.input, "simulation_input"),
        plant_model=plant_model,
        config=config,
        max_steps=args.max_steps,
        beam_width=args.beam_width,
    )
    payload = report.to_dict()
    payload["config"] = config_summary(config)
    _write_json(_output_path(args.output, "simulate_output"), payload)


def _run_adaptive_simulate(args: argparse.Namespace) -> None:
    config = _adaptive_enabled_config(load_controller_config(args.config))
    plant_model = ARXPlantModel.load_artifact(
        _input_path(args.artifact, "artifact"),
        pump_limits=config.pump,
    )
    report = run_adaptive_simulation(
        csv_path=_input_path(args.input, "simulation_input"),
        plant_model=plant_model,
        config=config,
        max_steps=args.max_steps,
        beam_width=args.beam_width,
    )
    payload = report.to_dict()
    payload["config"] = config_summary(config)
    _write_json(_output_path(args.output, "adaptive_simulate_output"), payload)


def _run_closed_loop(args: argparse.Namespace) -> None:
    config = load_controller_config(args.config)
    plant_model = ARXPlantModel.load_artifact(
        _input_path(args.artifact, "artifact"),
        pump_limits=config.pump,
    )
    state_payload = _read_json_object(
        _input_path(args.state_json, "state_json"),
        "state JSON",
    )
    state = ControllerState.from_mapping(state_payload)
    history = (
        _read_history_json(args.history_json)
        if args.history_json is not None
        else _default_history(state, plant_model.min_history_len, config)
    )
    now = _parse_optional_datetime(args.now)
    if now is None and args.state_json is None:
        now = state.timestamp
    result = run_closed_loop(
        state=state,
        history=history,
        plant_model=plant_model,
        config=config,
        now=now,
        used_today_pump_seconds=args.used_today_pump_seconds,
        beam_width=args.beam_width,
    )
    payload = result.to_dict()
    payload["config"] = config_summary(config)
    _write_json(_output_path(args.output, "closed_loop_output"), payload)


def _run_config_schema(args: argparse.Namespace) -> None:
    payload = default_config_schema()
    if args.output is None:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return
    _write_json(args.output, payload)


def _adaptive_enabled_config(config: ControllerConfig) -> ControllerConfig:
    if config.adaptive.enabled:
        return config
    return replace(config, adaptive=replace(config.adaptive, enabled=True))


def _read_json_object(path: str | Path, label: str) -> dict[str, Any]:
    json_path = Path(path)
    with json_path.open("r", encoding="utf-8-sig") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be an object")
    return payload


def _read_history_json(path: str | Path) -> tuple[PlantRecord, ...]:
    json_path = Path(path)
    with json_path.open("r", encoding="utf-8-sig") as fh:
        payload = json.load(fh)
    if not isinstance(payload, list):
        raise ValueError("history JSON root must be a list")
    history = tuple(_plant_record_from_mapping(item) for item in payload)
    if not history:
        raise ValueError("history JSON must not be empty")
    return history


def _plant_record_from_mapping(payload: Any) -> PlantRecord:
    if not isinstance(payload, dict):
        raise ValueError("history records must be objects")
    return PlantRecord(
        soil_moisture=float(payload["soil_moisture"]),
        temperature=float(payload["temperature"]),
        humidity=float(payload["humidity"]),
        light=float(payload["light"]),
        drip=float(payload.get("drip", 0.0)),
        mist=float(payload.get("mist", 0.0)),
        fan=float(payload.get("fan", 0.0)),
    )


def _default_history(
    state: ControllerState,
    min_history_len: int,
    config: Any,
) -> tuple[PlantRecord, ...]:
    drip = config.pump.to_duty(state.last_pump_seconds, config.step_seconds)
    record = state.to_plant_record(drip=drip)
    return (record,) * max(1, min_history_len)


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _input_path(value: str | Path | None, default_key: str) -> Path:
    if value is not None:
        return Path(value)
    default_value = DEFAULT_RUNTIME_PATHS[default_key]
    if default_value is None:
        raise ValueError(f"no default path configured for {default_key}")
    path = Path(default_value)
    if path.exists():
        return path
    project_relative = _project_root() / path
    if project_relative.exists():
        return project_relative
    return path


def _output_path(value: str | Path | None, default_key: str) -> Path:
    if value is not None:
        return Path(value)
    default_value = DEFAULT_RUNTIME_PATHS[default_key]
    if default_value is None:
        raise ValueError(f"no default path configured for {default_key}")
    return _project_root() / default_value


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    raise SystemExit(main())
