# MPC Config Reference

> Loại tài liệu: reference. File này chốt schema cấu hình mặc định cho task #001. Runtime code sẽ implement đúng contract này trong các task sau.

## 1. Controller Config

Config runtime được biểu diễn bằng `ControllerConfig` và có thể load từ JSON/YAML sau khi package được tạo. V2 không cần secret và không đọc Django settings.

```json
{
  "step_seconds": 300,
  "horizon_steps": 12,
  "target_band": {
    "low": 55.0,
    "high": 65.0
  },
  "pump": {
    "min_seconds": 0.0,
    "max_seconds": 300.0,
    "grid_seconds": 30.0
  },
  "disturbance_forecast": {
    "mode": "measured_hold"
  },
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
  "adaptive": {
    "enabled": false,
    "bias_window": 12,
    "max_abs_bias": 5.0
  },
  "actuator": {
    "enabled": false,
    "url": null,
    "bearer_token_env": null,
    "timeout_seconds": 5.0
  }
}
```

## 2. Default Decisions

| Field | Default | Reason |
|-------|---------|--------|
| `step_seconds` | `300` | Khớp chu kỳ mẫu 5 phút và ARX artifact hiện có. |
| `horizon_steps` | `12` | Nhiều hơn một hành động đơn lẻ nhưng vẫn nhẹ: 60 phút. |
| `target_band.low/high` | `55.0 / 65.0` | Band đã chốt trong PRD và onboarding. |
| `pump.min_seconds/max_seconds` | `0.0 / 300.0` | Một chu kỳ có thể tắt hoặc bật tối đa. |
| `pump.grid_seconds` | `30.0` | Tạo 11 ứng viên `0, 30, ..., 300`; đủ mịn cho v2, deterministic, không cần SciPy/CVXPY. |
| `soft_daily_pump_cap_seconds` | `1800.0` | Giới hạn mềm 30 phút/ngày cho demo khi chưa có flow rate; operator có thể override. |
| `stale_after_seconds` | `600` | Hai chu kỳ 5 phút, đúng rule fail-safe v3. |
| `adaptive.enabled` | `false` | V2 là MPC tĩnh; v3 mới bật bias adaptation. |
| `actuator.enabled` | `false` | V2 không điều khiển phần cứng; v3 chỉ auto execute khi config explicit hợp lệ. |

## 3. Cost Function

V2 grid solver sẽ tính tổng cost theo horizon:

```text
band_error = max(target_low - theta, theta - target_high, 0)
pump_ratio = pump_seconds / step_seconds
switch_ratio = abs(pump_seconds - previous_pump_seconds) / step_seconds
daily_excess_ratio = max(0, used_today + pump_seconds - soft_daily_cap) / step_seconds

stage_cost =
  band_violation * band_error^2
  + water_use * pump_ratio^2
  + switching * switch_ratio^2
  + daily_cap_excess * daily_excess_ratio^2

terminal_cost = terminal_band_violation * terminal_band_error^2
```

Notes:

- Band penalty được để cao hơn water/switching vì mục tiêu chính là giữ độ ẩm đất trong vùng an toàn.
- Daily cap là soft penalty, không phải hard stop, vì chưa có calibration flow rate.
- Safety gate vẫn có quyền clamp/fail-closed trước khi trả recommendation hoặc gửi actuator.

## 4. Public Dataclasses

Task implementation sau nên tạo dataclasses frozen cho các contract sau:

| Dataclass | Module | Purpose |
|-----------|--------|---------|
| `TargetBand` | `mpc.config` | `low`, `high` và validate `0 <= low < high <= 100`. |
| `PumpLimits` | `mpc.config` | `min_seconds`, `max_seconds`, `grid_seconds`; sinh candidate grid. |
| `CostWeights` | `mpc.config` | Nhóm weight cost. |
| `SafetyConfig` | `mpc.config` | Stale limit, state bounds, daily cap, fail-closed value. |
| `ControllerConfig` | `mpc.config` | Aggregate config V2/V3. |
| `ControllerState` | `mpc.state` | `timestamp`, `soil_moisture`, disturbances, `last_pump_seconds`, optional `run_id`. |
| `DisturbanceForecast` | `mpc.state` | Forecast measured-hold cho `temperature`, `humidity`, `light`. |
| `Recommendation` | `mpc.types` | Output chính của `recommend`. |
| `SimulationReport` | `mpc.simulation` | Band violation, pump seconds, switching count, objective cost. |
| `BiasState` | `mpc.adaptive` | Bias correction window và current bias cho v3. |
| `ActuatorCommand` | `mpc.actuator` | Payload HTTP v3 sau safety gate. |

## 5. Validation Rules

- Reject config nếu `step_seconds <= 0`, `horizon_steps < 1`, `grid_seconds <= 0`, hoặc `grid_seconds > max_seconds`.
- Reject config nếu target band nằm ngoài `[0, 100]` hoặc `low >= high`.
- Clamp pump command vào `[min_seconds, max_seconds]` tại safety boundary.
- Fail closed khi state thiếu, state không finite, timestamp stale, artifact/model lỗi, solver lỗi, hoặc actuator lỗi.
- Không hardcode actuator URL/token trong file config mẫu. V3 lấy token qua env name trong `bearer_token_env`.

