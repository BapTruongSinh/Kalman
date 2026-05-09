# MPC User Guide

`MPC/` là package/CLI độc lập cho controller tưới nước. V2 chạy recommendation một bước và simulation so sánh MPC với threshold baseline. V3 chạy adaptive simulation và `auto` closed-loop HTTP pilot có fail-safe.

## Chuẩn Bị Demo

Chạy các lệnh từ thư mục `MPC/`:

```powershell
cd MPC
```

CLI có default khi bạn bỏ trống path:

- ARX artifact: `..\ARX\arx_model.json`
- CSV trace: `..\ARX\greenhouse_data.csv`
- State mẫu: `examples\demo_state.json`
- Output: `reports\*.json`

Bạn vẫn có thể override bằng `--artifact`, `--state-json`, `--input`, `--output`, `--config`, `--beam-width`, hoặc `--max-steps`.

## Chạy Recommendation Một Bước

Recommendation trả một lệnh bơm cho state hiện tại.

```powershell
python -m mpc recommend
```

**Kết quả mong đợi**: file `reports\recommendation.json` có các field top-level `pump_seconds`, `step_seconds`, `predicted_soil_moisture`, `target_band`, `cost`, `safety_status`, và `reason`.

Khi không truyền `--history-json`, CLI tạo history tối thiểu từ state hiện tại đủ cho lag của ARX artifact.

## Chạy V2 Simulation

Simulation so sánh MPC với threshold baseline trên CSV trace.

```powershell
python -m mpc simulate --max-steps 288
```

**Kết quả mong đợi**: file `reports\v2_simulation.json` có `controllers.mpc`, `controllers.threshold`, và `baseline_definition`.

Các metric chính:

- `band_violation_seconds`: tổng thời gian độ ẩm đất nằm ngoài target band.
- `total_pump_seconds`: tổng số giây bơm.
- `switching_count`: số lần lệnh bơm đổi giữa hai step liên tiếp.
- `objective_cost`: tổng cost theo band, water, switching, soft daily cap, và terminal band.
- `mean_absolute_observation_error`: sai số trung bình tuyệt đối giữa forecast/controller state và observation trong fixture.

## Chạy V3 Adaptive Simulation

Adaptive simulation so sánh MPC tĩnh, AMPC có bias correction, và threshold baseline trên cùng input.

```powershell
python -m mpc adaptive-simulate --max-steps 288
```

**Kết quả mong đợi**: file `reports\v3_adaptive_simulation.json` có `controllers.mpc`, `controllers.ampc`, `controllers.threshold`, và `config.adaptive.enabled=true`.

AMPC dùng residual gần đây để bù bias forecast. Residual thiếu, stale, hoặc outlier bị bỏ qua; command vẫn đi qua solver và safety boundary như MPC v2.

## Chạy Auto Closed-Loop

`auto` là lệnh ngắn cho một bước closed-loop runtime.

```powershell
python -m mpc auto
```

**Kết quả mong đợi khi chưa cấu hình actuator**: file `reports\closed_loop_dry_run.json` có `actuator.executed=false`, `actuator.status="config_error"`, `actuator.command.pump_seconds=0.0`, và `alerts` chứa `actuator_disabled`.

Để bật HTTP actuator pilot:

1. Tạo config riêng.
2. Đặt `actuator.enabled=true`.
3. Đặt `actuator.url` thành endpoint actuator.
4. Đặt `actuator.bearer_token_env` thành tên biến môi trường chứa Bearer token.
5. Đặt token thật trong biến môi trường đó.
6. Chạy `python -m mpc auto --config path\to\config.json`.

Ví dụ cấu hình:

```json
{
  "actuator": {
    "enabled": true,
    "url": "http://127.0.0.1:8000/actuator",
    "bearer_token_env": "MPC_ACTUATOR_TOKEN",
    "timeout_seconds": 5.0
  }
}
```

Không ghi token thật vào file config. Output JSON không ghi token.

## Xuất Config Cho Website

Website có thể load default và phân nhóm field bằng:

```powershell
python -m mpc config-schema
```

Ghi ra file nếu cần:

```powershell
python -m mpc config-schema --output reports\config_schema.json
```

Schema gồm:

- `controller_defaults`: default `ControllerConfig`.
- `runtime_defaults`: path/output/default CLI values.
- `field_groups.user_inputs`: field người dùng nên nhập như target band, giới hạn bơm, soft daily cap, Kc cho tầng website sau này, và actuator config.
- `field_groups.system_defaults`: field có thể giữ mặc định như weights, horizon, step seconds, grid, beam width.

## Validation Nhanh

Chạy từ repo root:

```powershell
python -m pytest MPC\tests -q
python -m compileall -q MPC\mpc
```

**Kết quả mong đợi**: pytest pass toàn bộ MPC tests; `compileall` không in lỗi và trả exit code `0`.
