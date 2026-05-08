# MPC Codebase Onboarding

> Scope: `demo_kalman/MPC/`
> Last updated: 2026-05-09

## Current State

`MPC/` hiện có core package runtime `mpc/` và CLI v2. Task #001 đã chốt package architecture/config contract trong `CONFIG.md`; task #002 đã tạo config/state contracts, measured-hold disturbance forecast, và ARX plant adapter đọc `../ARX/arx_model.json`; task #003 đã tạo recommendation output contract, cost scoring, và deterministic beam-grid shooting solver; task #004 đã tạo `python -m mpc simulate` và `python -m mpc recommend`.

`recommend` ghi recommendation JSON theo public contract top-level: `pump_seconds`, `step_seconds`, `predicted_soil_moisture`, `target_band`, `cost`, `safety_status`, `reason`. `simulate` đọc CSV trace, so sánh MPC với threshold baseline, và ghi JSON report có band violation, total pump seconds, switching count, objective cost, cost breakdown, safety counts.

## Read Order

1. `MPC/PRD.md`
2. `MPC/docs/technical/ONBOARDING_ANSWERS.md`
3. `MPC/docs/technical/DECISIONS.md`
4. `MPC/docs/technical/CONFIG.md`
5. `MPC/docs/technical/ARCHITECTURE.md`
6. `MPC/docs/technical/API.md`
7. `MPC/TODO.md`
8. Task file trong `MPC/.tasks/`
9. `Kalman/docs/technical/CODEBASE_ONBOARDING.md`
10. `Kalman/docs/technical/AMPC_MODELING_HANDOFF.md`

## Boundaries

- `MPC/` là controller.
- `Kalman/` là estimator/live app.
- `ARX/` là artifact/research context.
- V2 không ghi DB và không điều khiển phần cứng.
- V2 CLI chạy độc lập Django/database.
- V3 closed-loop phải có fail-safe và fake actuator tests.

## Key Runtime Modules

| Module | Current role |
|--------|--------------|
| `mpc.config` | Dataclass config contract, JSON config loader |
| `mpc.state` | Controller state, plant record, measured-hold disturbance forecast |
| `mpc.plant.arx` | Load ARX artifact and forecast soil moisture |
| `mpc.solver.grid` | Deterministic beam-grid shooting recommendation solver |
| `mpc.solver.cost` | Trajectory cost and band error helpers |
| `mpc.simulation` | Threshold baseline, simulation runner, report metrics |
| `mpc.cli` / `mpc.__main__` | `simulate` and `recommend` CLI commands |

## Commands

```powershell
python -m pytest MPC\tests -q
cd MPC
python -m mpc recommend --artifact ..\ARX\arx_model.json --state-json state.json --output recommendation.json
python -m mpc simulate --artifact ..\ARX\arx_model.json --input ..\ARX\greenhouse_data.csv --output reports\v2_simulation.json --max-steps 288
```

## Validation Gates

Gate hiện tại cho MPC package:

```powershell
python -m pytest MPC\tests -q
python -m compileall -q MPC\mpc
```

Nếu task chạm `Kalman/` integration:

```powershell
cd Kalman\backend
python manage.py check
python -m pytest estimation\tests -q
```
