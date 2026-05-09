# MPC Codebase Onboarding

> Scope: `demo_kalman/MPC/`
> Last updated: 2026-05-09

## Current State

`MPC/` hiện có core package runtime `mpc/`, CLI v2/v3, validation suite, AMPC bias adaptation, và HTTP actuator pilot. Task #001 đã chốt package architecture/config contract trong `CONFIG.md`; task #002 đã tạo config/state contracts, measured-hold disturbance forecast, và ARX plant adapter đọc `../ARX/arx_model.json`; task #003 đã tạo recommendation output contract, cost scoring, và deterministic beam-grid shooting solver; task #004 đã tạo `python -m mpc simulate` và `python -m mpc recommend`; task #005 đã mở rộng validation suite; task #006 đã tạo bias adaptation layer và `python -m mpc adaptive-simulate`; task #007 đã tạo HTTP actuator pilot và `python -m mpc closed-loop`; task #008 đã đồng bộ demo workflow và validation docs.

`recommend` ghi recommendation JSON theo public contract top-level: `pump_seconds`, `step_seconds`, `predicted_soil_moisture`, `target_band`, `cost`, `safety_status`, `reason`. `simulate` đọc CSV trace, so sánh MPC với threshold baseline, và ghi JSON report có band violation, total pump seconds, switching count, objective cost, cost breakdown, safety counts, và observation-error metrics. `adaptive-simulate` ghi cùng schema report nhưng có thêm controller `ampc`; direct API `run_adaptive_simulation()` luôn bật bias adaptation nội bộ để tránh report AMPC giả khi caller truyền `ControllerConfig()` mặc định.

`closed-loop` đọc state/config/artifact, solve recommendation, rồi chỉ POST HTTP actuator khi `actuator.enabled=true`, URL hợp lệ, `actuator.bearer_token_env` tồn tại, và env token có giá trị. Nếu actuator config thiếu, token thiếu, HTTP lỗi, hoặc recommendation không `safe`, result fail-closed với `pump_seconds=0.0`, `safety_status="actuator_error"` hoặc safety status tương ứng, và `alerts` có lý do. Injected/fake actuator client vẫn phải đi qua validation config trước khi send.

## Read Order

1. `MPC/PRD.md`
2. `MPC/docs/technical/ONBOARDING_ANSWERS.md`
3. `MPC/docs/technical/DECISIONS.md`
4. `MPC/docs/technical/CONFIG.md`
5. `MPC/docs/technical/ARCHITECTURE.md`
6. `MPC/docs/technical/API.md`
7. `MPC/docs/technical/VALIDATION.md`
8. `MPC/docs/user/USER_GUIDE.md`
9. `MPC/TODO.md`
10. Task file trong `MPC/.tasks/`
11. `Kalman/docs/technical/CODEBASE_ONBOARDING.md`
12. `Kalman/docs/technical/AMPC_MODELING_HANDOFF.md`

## Boundaries

- `MPC/` là controller.
- `Kalman/` là estimator/live app.
- `ARX/` là artifact/research context.
- V2 không ghi DB và không điều khiển phần cứng.
- V2 CLI chạy độc lập Django/database.
- V3 closed-loop phải có fail-safe và fake actuator tests.
- Không hardcode actuator URL/token thật trong source, docs, test, hoặc review memory.

## Key Runtime Modules

| Module | Current role |
|--------|--------------|
| `mpc.config` | Dataclass config contract, strict JSON config loader, adaptive/actuator config |
| `mpc.state` | Controller state, plant record, measured-hold disturbance forecast |
| `mpc.plant.arx` | Load ARX artifact and forecast soil moisture |
| `mpc.solver.grid` | Deterministic beam-grid shooting recommendation solver with fail-closed validation |
| `mpc.solver.cost` | Trajectory cost and band error helpers |
| `mpc.adaptive` | Bias estimator, bias state, and bias-corrected plant model wrapper |
| `mpc.simulation` | Threshold baseline, v2/v3 simulation runners, report metrics |
| `mpc.actuator` | Actuator command/result contracts and HTTP client with Bearer token from env |
| `mpc.closed_loop` | Closed-loop service that combines solver output, fail-safe command selection, and actuator result |
| `mpc.cli` / `mpc.__main__` | `simulate`, `recommend`, `adaptive-simulate`, and `closed-loop` CLI commands |

## Demo Commands

Chạy từ thư mục `MPC/`:

```powershell
python -m mpc recommend --artifact ..\ARX\arx_model.json --state-json examples\demo_state.json --output reports\recommendation.json --now 2026-05-09T10:00:00+00:00
python -m mpc simulate --artifact ..\ARX\arx_model.json --input ..\ARX\greenhouse_data.csv --output reports\v2_simulation.json --max-steps 288
python -m mpc adaptive-simulate --artifact ..\ARX\arx_model.json --input ..\ARX\greenhouse_data.csv --output reports\v3_adaptive_simulation.json --max-steps 288
python -m mpc closed-loop --artifact ..\ARX\arx_model.json --state-json examples\demo_state.json --config examples\closed_loop_dry_run.json --output reports\closed_loop_dry_run.json --now 2026-05-09T10:00:00+00:00
```

## Validation Gates

Gate hiện tại cho MPC package:

```powershell
python -m pytest MPC\tests -q
python -m compileall -q MPC\mpc
```

CLI smoke gate nhanh:

```powershell
cd MPC
python -m mpc recommend --artifact ..\ARX\arx_model.json --state-json examples\demo_state.json --output reports\recommendation.json --now 2026-05-09T10:00:00+00:00
python -m mpc simulate --artifact ..\ARX\arx_model.json --input ..\ARX\greenhouse_data.csv --output reports\v2_simulation.json --max-steps 3 --beam-width 4
python -m mpc adaptive-simulate --artifact ..\ARX\arx_model.json --input ..\ARX\greenhouse_data.csv --output reports\v3_adaptive_simulation.json --max-steps 3 --beam-width 4
python -m mpc closed-loop --artifact ..\ARX\arx_model.json --state-json examples\demo_state.json --config examples\closed_loop_dry_run.json --output reports\closed_loop_dry_run.json --now 2026-05-09T10:00:00+00:00 --beam-width 4
```

Expected output chi tiết nằm trong `MPC/docs/technical/VALIDATION.md`.

Nếu task chạm `Kalman/` integration:

```powershell
cd Kalman\backend
python manage.py check
python -m pytest estimation\tests -q
```
