# MPC Interface Contracts

> Đây là contract cho CLI/module output. Chưa có HTTP API trong v2.

## 1. Recommendation Input

```json
{
  "run_id": 1,
  "timestamp": "2026-05-08T10:00:00Z",
  "kf_x_posterior": 58.2,
  "raw_soil_moisture": 58.5,
  "temperature": 27.0,
  "humidity": 74.0,
  "light": 300.0,
  "last_pump_seconds": 0.0
}
```

Rules:

- Ưu tiên `kf_x_posterior`.
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
  "reason": "below_target_margin"
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
  }
}
```

V2 grid candidates là `0, 30, 60, ..., 300` giây bơm. Runtime hiện dùng deterministic beam-grid shooting để tránh enumerate toàn bộ `11^12` horizon; mặc định giữ 32 sequence tốt nhất mỗi bước. Solver trả lệnh đầu tiên của sequence có cost thấp nhất trong beam đã xét. Với horizon nhỏ hoặc `beam_width` đủ lớn, kết quả trùng exhaustive grid search.

## 2.2 Simulation Report Output

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
        "terminal": 0.0,
        "water": 0.0,
        "switching": 0.0,
        "daily_cap": 0.0
      },
      "final_soil_moisture": 60.0,
      "safety_counts": {"safe": 288}
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
        "terminal": 0.0,
        "water": 0.0,
        "switching": 0.0,
        "daily_cap": 0.0
      },
      "final_soil_moisture": 60.0,
      "safety_counts": {"not_applicable": 288}
    }
  }
}
```

Threshold baseline được định nghĩa rõ: nếu độ ẩm đất hiện tại thấp hơn `target_band.low` thì bơm `pump.max_seconds`; ngược lại bơm `pump.min_seconds`.

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
- Timeout/retry policy: task #007 sẽ chốt.
