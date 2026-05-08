# MPC Validation Gates

> Loại tài liệu: reference. File này mô tả các gate kiểm thử bắt buộc trước khi xem một task MPC là hoàn tất.

## Gate Chung

Chạy từ repo root:

```powershell
python -m pytest MPC\tests -q
python -m compileall -q MPC\mpc
```

Task chỉ được báo hoàn tất khi cả hai lệnh pass, trừ khi task là docs-only và đã ghi rõ lý do không chạy runtime tests.

## V2 Coverage Hiện Có

| Nhóm | File test | Mục tiêu |
|------|-----------|----------|
| Config | `MPC/tests/test_config.py` | Default contract, pump grid, JSON config loading, validation lỗi |
| State | `MPC/tests/test_state.py` | Kalman posterior fallback raw, disturbance hold, state payload validation |
| ARX plant | `MPC/tests/test_arx_plant.py` | Load artifact, input/output lag mapping, pump duty mapping, invalid artifact |
| Solver | `MPC/tests/test_grid_solver.py` | Determinism, bounds, stale/future/missing/model-error fail-closed |
| CLI + report | `MPC/tests/test_cli_simulation.py` | `recommend`/`simulate` smoke, invalid input, public JSON contract |
| Simulation regression | `MPC/tests/test_simulation_regression.py` | Stable MPC-vs-threshold fixture and report metric regression |

## CLI Smoke Gates

`recommend` phải ghi JSON top-level đúng contract:

```powershell
cd MPC
python -m mpc recommend --artifact ..\ARX\arx_model.json --state-json state.json --output recommendation.json
```

Output tối thiểu phải có:

- `pump_seconds`
- `step_seconds`
- `predicted_soil_moisture`
- `target_band`
- `cost`
- `safety_status`
- `reason`

`simulate` phải ghi report có `controllers.mpc`, `controllers.threshold`, `baseline_definition`, và metric:

- `band_violation_steps`
- `band_violation_seconds`
- `total_pump_seconds`
- `switching_count`
- `objective_cost`
- `cost_breakdown`

## Security And Fail-Safe Gates

- CLI phải trả exit code khác `0` khi artifact, state JSON, config JSON, hoặc CSV input không hợp lệ.
- CLI không được ghi output file khi input validation fail.
- Solver phải fail closed với stale sample, future sample ngoài clock skew, missing state, model error, hoặc config/runtime input không hợp lệ.
- V2 không gọi Django, database, HTTP actuator, hoặc phần cứng thật.

## Regression Gate Cho Simulation

Simulation regression dùng fixture synthetic ổn định, không dùng production data. Fixture phải bảo vệ các invariant:

- Report luôn có đủ `mpc` và `threshold`.
- MPC và threshold cùng dùng cùng plant/config baseline.
- Objective cost không cộng soft daily cap xuyên qua nhiều ngày lịch.
- Public report metric không đổi tên khi chưa cập nhật `API.md` và tests tương ứng.
