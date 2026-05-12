# MPC Interface Contracts

> Đây là contract cho CLI/module output. Chưa có HTTP API trong v2.

## 1. Recommendation Input

```json
{
  "run_id": 1,
  "timestamp": "2026-05-08T10:00:00Z",
  "kf_x_posterior": 58.2,
  "kf_R": 1.4,
  "raw_soil_moisture": 58.5,
  "temperature": 27.0,
  "humidity": 74.0,
  "light": 300.0,
  "last_pump_seconds": 0.0
}
```

Rules:

- Ưu tiên `kf_x_posterior` khi Kalman confidence còn tin được (`kf_R <= 15` hoặc không có `kf_R` trong payload cũ).
- Nếu `kf_R > 15` và có `raw_soil_moisture`, controller dùng raw sensor thay posterior.
- Nếu thiếu `kf_x_posterior`, dùng `raw_soil_moisture`.
- Nếu cả hai thiếu, sample stale, hoặc timestamp ở tương lai quá clock skew nhỏ, recommendation phải fail closed.
- Khi forecast, state mới nhất là source of truth; solver thay latest history record bằng `state.to_plant_record()`.

## 2. Recommendation Output

```json
{
  "pump_seconds": 60.0,
  "step_seconds": 300,
  "predicted_soil_moisture": [58.2, 58.4, 58.8],
  "target_band": {"low": 55.0, "high": 65.0},
  "cost": 12.34,
  "safety_status": "safe",
  "reason": "above_raw_stress",
  "fao56": {
    "initial_theta": 0.315,
    "initial_dr": 1.5,
    "taw": 51.0,
    "raw": 25.5,
    "ks": 1.0,
    "et0_step": 0.05,
    "etc_adj": 0.05,
    "irrigation_depth_mm": 19.2,
    "predicted_dr": [0.0, 0.05, 0.1]
  }
}
```

Allowed `safety_status` values:

- `safe`
- `pump_off_failsafe`
- `config_error`
- `stale_sample`
- `model_error`
- `solver_error`
- `actuator_error`

## 2.1 Config Contract

Default config được định nghĩa ở [`CONFIG.md`](./CONFIG.md). Các field tối thiểu cho v2:

```json
{
  "step_seconds": 300,
  "horizon_steps": 12,
  "target_band": {"low": 55.0, "high": 65.0},
  "pump": {"min_seconds": 0.0, "max_seconds": 300.0, "grid_seconds": 30.0},
  "cost": {
    "band_violation": 10.0,
    "terminal_band_violation": 20.0,
    "water_use": 0.2,
    "switching": 0.5,
    "daily_cap_excess": 2.0
  },
  "safety": {
    "state_min": 0.0,
    "state_max": 100.0,
    "stale_after_seconds": 600,
    "soft_daily_pump_cap_seconds": 1800.0,
    "fail_closed_pump_seconds": 0.0
  },
  "fao56": {
    "crop_kc": 1.0,
    "soil_type": "loam",
    "theta_fc": 0.32,
    "theta_wp": 0.15,
    "theta_sat": 0.45,
    "root_depth_m": 0.3,
    "depletion_fraction_p": 0.5,
    "et0_hour_mm": 0.6,
    "pump_efficiency": 0.8,
    "pump_flow_lps": 0.02,
    "irrigation_area_m2": 0.25
  }
}
```

V2 grid candidates là `0, 30, 60, ..., 300` giây bơm. Runtime hiện dùng deterministic beam-grid shooting để tránh enumerate toàn bộ `11^12` horizon; mặc định giữ 32 sequence tốt nhất mỗi bước. Solver trả lệnh đầu tiên của sequence có cost thấp nhất trong beam đã xét. Với horizon nhỏ hoặc `beam_width` đủ lớn, kết quả trùng exhaustive grid search.

CLI có thể chạy với default khi bỏ trống path:

```powershell
python -m mpc recommend
python -m mpc simulate --max-steps 288
python -m mpc adaptive-simulate --max-steps 288
python -m mpc auto
```

Default runtime path nằm trong `mpc.schema.DEFAULT_RUNTIME_PATHS`: artifact `../ARX/arx_model.json`, state demo `examples/demo_state.json`, simulation input `../ARX/greenhouse_data.csv`, và output trong `reports/`.

## 2.1.1 Config Schema Output

`python -m mpc config-schema` xuất JSON để website load default và render form cấu hình:

```json
{
  "schema_version": 1,
  "controller_defaults": {
    "step_seconds": 300,
    "horizon_steps": 12,
    "target_band": {"low": 55.0, "high": 65.0}
  },
  "runtime_defaults": {
    "artifact": "../ARX/arx_model.json",
    "state_json": "examples/demo_state.json",
    "simulation_input": "../ARX/greenhouse_data.csv",
    "beam_width": 32,
    "max_steps": null
  },
  "field_groups": {
    "user_inputs": [
      {"name": "target_band.low", "type": "number"},
      {"name": "target_band.high", "type": "number"},
      {"name": "pump.max_seconds", "type": "number"},
      {"name": "safety.soft_daily_pump_cap_seconds", "type": "number"},
      {"name": "crop.kc", "type": "number", "runtime_field": false},
      {"name": "fao56.crop_kc", "type": "number"},
      {"name": "fao56.soil_type", "type": "enum"},
      {"name": "fao56.root_depth_m", "type": "number"},
      {"name": "fao56.et0_hour_mm", "type": "number"},
      {"name": "fao56.pump_flow_lps", "type": "number"}
    ],
    "system_defaults": [
      {"name": "cost.water_use", "type": "number"},
      {"name": "cost.switching", "type": "number"},
      {"name": "beam_width", "type": "integer"}
    ]
  }
}
```

`crop.kc` được xuất để website có chỗ lưu/hiển thị hệ số cây trồng, nhưng MPC runtime hiện chưa dùng trực tiếp field này. Token actuator thật không xuất hiện trong schema; schema chỉ cho phép cấu hình tên biến môi trường `actuator.bearer_token_env`.

`theta_sat=0.45` is the first-version default wet-end mapping for the FAO-56 sensor scale. `crop.kc` is kept as a legacy schema alias; runtime water-balance code uses `fao56.crop_kc` and the other `fao56.*` fields.

## 2.1.2 FAO-56 Objective

The recommendation solver evaluates candidate pump sequences with root-zone depletion `Dr` as the primary control state. `predicted_soil_moisture` remains in sensor-percent units only for dashboard compatibility.

Stage cost:

```text
stress_error = max(0, Dr_k - RAW)
overwater_error = max(0, -Dr_raw_next)
water_term = (u_k / pump_max_seconds)^2
switch_term = ((u_k - u_k-1) / pump_max_seconds)^2
```

Weights map from the existing cost config:

- `stress_error` and `overwater_error`: `cost.band_violation`
- `water_term`: `cost.water_use`
- `switch_term`: `cost.switching`

Terminal cost:

```text
terminal_cost = cost.terminal_band_violation * max(0, Dr_H - RAW)^2
```

`Dr_raw_next` is checked before clamping so over-irrigation is penalized. The final transition still clamps with `Dr_next = clamp(Dr_raw_next, 0, TAW)`.

## 2.1.3 Legacy Band Objective Reference

Objective cost dùng band tracking theo độ lệch khỏi band. Water và switching normalize bằng `pump.max_seconds`; soft daily cap normalize bằng `soft_daily_pump_cap_seconds` theo tổng planned pump seconds trong horizon:

```text
J =
sum_i [
  w_band * band_error_i^2
  + w_water * (u_i / u_max)^2
  + w_switch * ((u_i - u_{i-1}) / u_max)^2
]
+ w_daily * daily_excess_ratio^2
+ w_terminal * band_error_H^2
```

`band_error_i = max(0, target_low - theta_i) + max(0, theta_i - target_high)`.

## 2.2 Simulation Report Output

`objective_cost` and `cost_breakdown` use the FAO-56 `Dr/RAW`
stress/overwater objective. `band_violation_*` remains a legacy
sensor-percent diagnostic for comparing dashboard-visible trajectories.

`python -m mpc simulate` ghi JSON report có dạng:

```json
{
  "generated_at": "2026-05-09T10:00:00+00:00",
  "input_rows": 289,
  "warmup_rows": 1,
  "simulated_steps": 288,
  "baseline_definition": {
    "name": "threshold_low_full_pump",
    "rule": "pump max_seconds when soil_moisture is below target_band.low; otherwise pump min_seconds",
    "target_band": {"low": 55.0, "high": 65.0},
    "pump_seconds_below_low": 300.0,
    "pump_seconds_at_or_above_low": 0.0
  },
  "controllers": {
    "mpc": {
      "band_violation_steps": 0,
      "band_violation_seconds": 0,
      "band_violation_error_sum": 0.0,
      "total_pump_seconds": 0.0,
      "switching_count": 0,
      "objective_cost": 0.0,
      "cost_breakdown": {
        "band": 0.0,
        "overwater": 0.0,
        "terminal": 0.0,
        "water": 0.0,
        "switching": 0.0,
        "daily_cap": 0.0
      },
      "final_soil_moisture": 60.0,
      "safety_counts": {"safe": 288},
      "mean_absolute_observation_error": 0.0,
      "max_absolute_observation_error": 0.0
    },
    "threshold": {
      "band_violation_steps": 0,
      "band_violation_seconds": 0,
      "band_violation_error_sum": 0.0,
      "total_pump_seconds": 0.0,
      "switching_count": 0,
      "objective_cost": 0.0,
      "cost_breakdown": {
        "band": 0.0,
        "overwater": 0.0,
        "terminal": 0.0,
        "water": 0.0,
        "switching": 0.0,
        "daily_cap": 0.0
      },
      "final_soil_moisture": 60.0,
      "safety_counts": {"not_applicable": 288},
      "mean_absolute_observation_error": 0.0,
      "max_absolute_observation_error": 0.0
    }
  }
}
```

Threshold baseline được định nghĩa rõ: nếu độ ẩm đất hiện tại thấp hơn `target_band.low` thì bơm `pump.max_seconds`; ngược lại bơm `pump.min_seconds`.

## 2.3 Adaptive Simulation Report Output

`python -m mpc adaptive-simulate` ghi cùng schema report với `simulate`, nhưng `controllers` có thêm `ampc` để so sánh trực tiếp v2 MPC và v3 AMPC:

```json
{
  "controllers": {
    "mpc": {"mean_absolute_observation_error": 5.0},
    "ampc": {"mean_absolute_observation_error": 1.25},
    "threshold": {"mean_absolute_observation_error": 5.0}
  },
  "config": {
    "adaptive": {
      "enabled": true,
      "bias_window": 12,
      "max_abs_bias": 5.0
    }
  }
}
```

`ampc` dùng bias correction từ residual gần đây trước khi forecast horizon. Residual thiếu, stale, hoặc outlier bị bỏ qua; khi bị bỏ qua, lệnh bơm vẫn đi qua solver/safety boundary như MPC v2.

## 3. Actuator Payload (v3)

```json
{
  "command_id": "uuid",
  "timestamp": "2026-05-08T10:00:00Z",
  "run_id": 1,
  "pump_seconds": 60.0,
  "step_seconds": 300,
  "mode": "auto",
  "reason": "mpc_recommendation_safe",
  "safety_status": "safe"
}
```

HTTP:

- Method: `POST`
- Auth: `Authorization: Bearer <token>`
- Timeout: `actuator.timeout_seconds`, mặc định 5 giây.
- Retry: không retry trong pilot đầu tiên. HTTP lỗi trả fail-closed result và alert.
- Token không xuất hiện trong output JSON.

## 3.1 Closed-Loop Result Output

`python -m mpc closed-loop` đọc state, solve recommendation, rồi chỉ POST actuator khi `actuator.enabled=true`, `actuator.url` tồn tại, `actuator.bearer_token_env` tồn tại, và env đó có token.

```json
{
  "recommendation": {
    "pump_seconds": 300.0,
    "step_seconds": 300,
    "predicted_soil_moisture": [56.0],
    "target_band": {"low": 55.0, "high": 65.0},
    "cost": 0.2,
    "safety_status": "safe",
    "reason": "below_target_margin"
  },
  "actuator": {
    "executed": true,
    "status": "sent",
    "command": {
      "command_id": "uuid",
      "timestamp": "2026-05-08T10:00:00+00:00",
      "run_id": 1,
      "pump_seconds": 300.0,
      "step_seconds": 300,
      "mode": "auto",
      "reason": "mpc_recommendation_safe",
      "safety_status": "safe"
    },
    "http_status_code": 200,
    "alert": null,
    "error": null
  },
  "alerts": []
}
```

Fail-safe rules:

- Nếu state stale, state thiếu, model lỗi, solver lỗi, hoặc recommendation không `safe`, actuator command dùng `pump_seconds=0.0`.
- Nếu config actuator thiếu URL/token/env hoặc HTTP POST lỗi, result trả `executed=false`, command fail-closed `pump_seconds=0.0`, `safety_status="actuator_error"`, và `alerts` có lý do.
- CLI vẫn ghi output JSON cho lỗi fail-safe đã kiểm soát; input JSON/config/artifact hỏng vẫn exit non-zero và không ghi output.
