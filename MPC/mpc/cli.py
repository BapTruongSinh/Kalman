"""Command line entry point for standalone MPC workflows."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from mpc.config import load_controller_config
from mpc.plant import ARXPlantModel
from mpc.simulation import run_simulation
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
    recommend.add_argument("--artifact", required=True)
    recommend.add_argument("--state-json", required=True)
    recommend.add_argument("--output", required=True)
    recommend.add_argument("--config", default=None)
    recommend.add_argument("--history-json", default=None)
    recommend.add_argument("--now", default=None)
    recommend.add_argument("--used-today-pump-seconds", type=float, default=0.0)
    recommend.add_argument("--beam-width", type=int, default=32)

    simulate = subparsers.add_parser(
        "simulate",
        help="compare v2 MPC against threshold baseline over CSV input",
    )
    simulate.add_argument("--artifact", required=True)
    simulate.add_argument("--input", required=True)
    simulate.add_argument("--output", required=True)
    simulate.add_argument("--config", default=None)
    simulate.add_argument("--max-steps", type=int, default=None)
    simulate.add_argument("--beam-width", type=int, default=32)
    return parser


def _run_recommend(args: argparse.Namespace) -> None:
    config = load_controller_config(args.config)
    plant_model = ARXPlantModel.load_artifact(
        args.artifact,
        pump_limits=config.pump,
    )
    state_payload = _read_json_object(args.state_json, "state JSON")
    state = ControllerState.from_mapping(state_payload)
    history = (
        _read_history_json(args.history_json)
        if args.history_json is not None
        else _default_history(state, plant_model.min_history_len, config)
    )
    recommendation = GridShootingSolver(
        config,
        beam_width=args.beam_width,
    ).recommend(
        state=state,
        history=history,
        plant_model=plant_model,
        now=_parse_optional_datetime(args.now),
        used_today_pump_seconds=args.used_today_pump_seconds,
    )
    _write_json(args.output, recommendation.to_dict())


def _run_simulate(args: argparse.Namespace) -> None:
    config = load_controller_config(args.config)
    plant_model = ARXPlantModel.load_artifact(
        args.artifact,
        pump_limits=config.pump,
    )
    report = run_simulation(
        csv_path=args.input,
        plant_model=plant_model,
        config=config,
        max_steps=args.max_steps,
        beam_width=args.beam_width,
    )
    payload = report.to_dict()
    payload["config"] = config_summary(config)
    _write_json(args.output, payload)


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


if __name__ == "__main__":
    raise SystemExit(main())
