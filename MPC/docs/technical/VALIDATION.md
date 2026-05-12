# MPC Validation Gates

> Loại tài liệu: reference. File này mô tả các gate kiểm thử bắt buộc trước khi xem một task MPC là hoàn tất.

## Gate Chung

Chạy từ repo root:

```powershell
python -m pytest MPC\tests -q
python -m compileall -q MPC\mpc
```

Expected:

- `pytest` pass toàn bộ test trong `MPC\tests`.
- `compileall` không in lỗi và trả exit code `0`.
- Nếu task là docs-only, vẫn chạy gate chung khi docs mô tả runtime/CLI.

## V2/V3 Coverage Hiện Có

| Nhóm | File test | Mục tiêu |
|------|-----------|----------|
| Config | `MPC/tests/test_config.py` | Default contract, pump grid, JSON config loading, validation lỗi |
| State | `MPC/tests/test_state.py` | Kalman posterior fallback raw, disturbance hold, state payload validation |
| ARX plant | `MPC/tests/test_arx_plant.py` | Load artifact, input/output lag mapping, pump duty mapping, invalid artifact |
| Solver | `MPC/tests/test_grid_solver.py` | Determinism, bounds, stale/future/missing/model-error fail-closed |
| Adaptive bias | `MPC/tests/test_adaptive_bias.py` | Guard missing/stale/outlier residual, clipped bias, recursive bias-corrected forecast |
| Actuator/closed-loop | `MPC/tests/test_actuator_closed_loop.py` | Fake HTTP POST, Bearer header, stale fail-closed command, missing token, injected-client guard, HTTP failure |
| CLI + report | `MPC/tests/test_cli_simulation.py` | `recommend`/`simulate`/`adaptive-simulate`/`auto`/`config-schema` smoke, default args, invalid input, public JSON contract |
| Simulation regression | `MPC/tests/test_simulation_regression.py` | Stable MPC-vs-threshold fixture, AMPC synthetic mismatch improvement, and report metric regression |

## CLI Smoke Gates

Chạy từ thư mục `MPC/`.

### V2 Recommend

```powershell
python -m mpc recommend --beam-width 4
```

Expected output file:

- Có top-level `pump_seconds`, `step_seconds`, `predicted_soil_moisture`, `target_band`, `cost`, `safety_status`, `reason`, `fao56`.
- `fao56` có `initial_theta`, `initial_dr`, `taw`, `raw`, `ks`, `et0_step`, `etc_adj`, `irrigation_depth_mm`, và `predicted_dr`.
- Không wrap trong `recommendation`.
- Không có `config` envelope.

### V2 Simulation

```powershell
python -m mpc simulate --max-steps 3 --beam-width 4
```

Expected output file:

- Có `controllers.mpc`.
- Có `controllers.threshold`.
- Có `baseline_definition.name="threshold_low_full_pump"`.
- Có metric `band_violation_steps`, `band_violation_seconds`, `total_pump_seconds`, `switching_count`, `objective_cost`, `cost_breakdown`, `mean_absolute_observation_error`, `max_absolute_observation_error`.
- `objective_cost` và `cost_breakdown` dùng FAO-56 `Dr/RAW` stress, overwater, water, switching, daily-cap, và terminal-stress objective. `band_violation_*` chỉ còn là metric sensor-percent legacy để so sánh dashboard.

### V3 Adaptive Simulation

```powershell
python -m mpc adaptive-simulate --max-steps 3 --beam-width 4
```

Expected output file:

- Có `controllers.mpc`.
- Có `controllers.ampc`.
- Có `controllers.threshold`.
- Có `config.adaptive.enabled=true`.
- Các controller có cùng metric chính như `simulate`.

### V3 Auto Dry Check

```powershell
python -m mpc auto --beam-width 4
```

Expected output file:

- Có `recommendation`.
- Có `actuator.command`.
- Có `alerts`.
- `actuator.executed=false`.
- `actuator.status="config_error"`.
- `actuator.command.pump_seconds=0.0`.
- `actuator.command.safety_status="actuator_error"`.
- `alerts` chứa `actuator_disabled`.

### Config Schema

```powershell
python -m mpc config-schema
```

Expected stdout:

- Có `schema_version=1`.
- Có `controller_defaults`.
- Có `runtime_defaults.artifact="../ARX/arx_model.json"`.
- Có `field_groups.user_inputs` chứa `target_band.low`, `target_band.high`, `pump.max_seconds`, `safety.soft_daily_pump_cap_seconds`, và `crop.kc`.
- Không có token actuator thật; chỉ có field tên env `actuator.bearer_token_env`.

## Security And Fail-Safe Gates

- CLI phải trả exit code khác `0` khi artifact, state JSON, config JSON, hoặc CSV input không hợp lệ.
- CLI không được ghi output file khi input validation fail.
- Solver phải fail closed với stale sample, future sample ngoài clock skew, missing state, model error, hoặc config/runtime input không hợp lệ.
- Bias adaptation phải bỏ qua residual thiếu, stale, hoặc outlier thay vì khuếch đại thành command unsafe.
- Closed-loop chỉ POST actuator khi `actuator.enabled=true`, URL hợp lệ, env token name tồn tại, và token env có giá trị.
- Closed-loop phải validate actuator config trước khi dùng injected/fake client.
- Closed-loop không được ghi token vào output JSON hoặc test log.
- Actuator HTTP failure phải trả command fail-closed và alert.
- V2 không gọi Django, database, HTTP actuator, hoặc phần cứng thật.

## Green-House Integration Gates

Sau khi tích hợp FAO-56 vào `Green-House/`, chạy thêm từ repo root hoặc thư mục con tương ứng:

```powershell
cd Green-House\backend
python manage.py test api
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python -m pip install -r requirements-local.txt --dry-run
```

```powershell
cd Green-House\frontend
npm test
npm run build
```

```powershell
python -m pytest Kalman\tests -q
python -m pytest MPC\tests -q
python -m compileall -q Kalman\kalman MPC\mpc Green-House\backend\api Green-House\backend\config
```

Integration scenarios cần có coverage:

- Wet state tạo `Dr = 0` và không tưới thêm.
- Dry/stressed state có `Dr > RAW` và đề xuất pump non-zero khi an toàn.
- ET0 unavailable tạo recommendation fail-closed, pump `0`, không queue actuator command.
- Persisted FAO config invalid tạo audit `config_error` trước khi gọi ET0/solver.
- User không đọc/sửa/chạy greenhouse của user khác.
- Actuator command chỉ được tạo khi control mode `AUTO`, profile bật actuator, có pump device, và recommendation `safe`.

## Regression Gate Cho Simulation

Simulation regression dùng fixture synthetic ổn định, không dùng production data. Fixture phải bảo vệ các invariant:

- Report v2 luôn có đủ `mpc` và `threshold`; report v3 adaptive luôn có thêm `ampc`.
- MPC và threshold cùng dùng cùng plant/config baseline.
- Synthetic bias mismatch phải chứng minh `ampc.mean_absolute_observation_error < mpc.mean_absolute_observation_error`.
- Objective cost không cộng soft daily cap xuyên qua nhiều ngày lịch.
- Objective cost normalize water/switching bằng `pump.max_seconds`, không dùng `step_seconds`.
- Solver objective dùng FAO-56 `Dr/TAW/RAW`; `predicted_soil_moisture` chỉ là compatibility output theo sensor percent.
- Soft daily cap penalty dùng tổng planned excess chia cho `soft_daily_pump_cap_seconds`.
- Public report metric không đổi tên khi chưa cập nhật `API.md` và tests tương ứng.
