# MPC Config Reference

> Loại tài liệu: reference. File này chốt schema cấu hình runtime cho MPC/AMPC.

## 1. Controller Config

Config runtime được biểu diễn bằng `ControllerConfig` và có thể load từ JSON. V2 không cần secret và không đọc Django settings.

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
| `horizon_steps` | `12` | Horizon 60 phút. |
| `target_band.low/high` | `55.0 / 65.0` | Band đã chốt trong PRD và onboarding. |
| `pump.min_seconds/max_seconds` | `0.0 / 300.0` | Một chu kỳ có thể tắt hoặc bật tối đa. |
| `pump.grid_seconds` | `30.0` | Tạo 11 ứng viên `0, 30, ..., 300`; deterministic, không cần SciPy/CVXPY. |
| `soft_daily_pump_cap_seconds` | `1800.0` | Giới hạn mềm 30 phút/ngày cho demo khi chưa có flow rate. |
| `stale_after_seconds` | `600` | Hai chu kỳ 5 phút, đúng rule fail-safe v3. |
| `adaptive.enabled` | `false` | V2 là MPC tĩnh; v3 mới bật bias adaptation. |
| `adaptive.bias_window` | `12` | Số residual gần nhất dùng để tính moving-average bias. |
| `adaptive.max_abs_bias` | `5.0` | Giới hạn tuyệt đối cho bias correction theo đơn vị độ ẩm đất. |
| `actuator.enabled` | `false` | V2 không điều khiển phần cứng; v3 chỉ auto execute khi config explicit hợp lệ. |
| `actuator.url` | `null` | HTTP endpoint chỉ cấu hình ngoài code. |
| `actuator.bearer_token_env` | `null` | Tên biến môi trường chứa Bearer token; output không ghi token. |
| `actuator.timeout_seconds` | `5.0` | Timeout POST actuator cho pilot đầu tiên. |

## 3. Cost Function

V2 grid solver tính tổng cost theo horizon:

```text
band_error_i =
  max(0, target_low - theta_i)
  + max(0, theta_i - target_high)

stage_cost_i =
  band_violation * band_error_i^2
  + water_use * (pump_seconds_i / pump.max_seconds)^2
  + switching * ((pump_seconds_i - pump_seconds_{i-1}) / pump.max_seconds)^2

daily_excess_ratio =
  max(0, used_today + sum(pump_seconds_i) - soft_daily_cap) / soft_daily_cap

daily_cap_cost = daily_cap_excess * daily_excess_ratio^2
terminal_cost = terminal_band_violation * band_error_H^2

total_cost = sum(stage_cost_i) + daily_cap_cost + terminal_cost
```

Notes:

- `band_error_i` là độ lệch khỏi target band, không phải biến 0/1.
- Water và switching normalize bằng `pump.max_seconds`, không phải `step_seconds`, để cost bám theo biên điều khiển thật của bơm.
- Daily cap là soft penalty theo tổng planned pump seconds trong horizon. Với simulation report nhiều ngày, cap được reset theo từng ngày lịch.
- Terminal penalty giữ trạng thái cuối horizon trong vùng an toàn.
- `PumpLimits.to_duty()` vẫn dùng `pump_seconds / step_seconds` vì đó là mapping sang ARX input `Drip`, không phải objective cost normalization.

## 4. Config Schema Cho Website

`python -m mpc config-schema` xuất schema JSON từ `mpc.schema.default_config_schema()`. Schema này dùng cho website hoặc API wrapper đọc default và phân nhóm field:

- `controller_defaults`: toàn bộ default `ControllerConfig`.
- `runtime_defaults`: path mặc định cho artifact/state/input/output, `beam_width`, `max_steps`, và `used_today_pump_seconds`.
- `field_groups.user_inputs`: field nên cho người dùng nhập hoặc chọn trên UI, gồm target band, giới hạn bơm, soft daily cap, actuator config, và `crop.kc`.
- `field_groups.system_defaults`: field nên giữ mặc định ban đầu, gồm weight cost, horizon, step seconds, grid, adaptive bias bounds, và beam width.

`crop.kc` là field dành cho website/agronomy profile sau này, có `runtime_field=false` vì MPC runtime hiện chưa dùng trực tiếp. Token thật không nằm trong schema; actuator chỉ nhận tên biến môi trường qua `actuator.bearer_token_env`.

## 5. Public Dataclasses

| Dataclass | Module | Purpose |
|-----------|--------|---------|
| `TargetBand` | `mpc.config` | `low`, `high` và validate `0 <= low < high <= 100`. |
| `PumpLimits` | `mpc.config` | `min_seconds`, `max_seconds`, `grid_seconds`; sinh candidate grid. |
| `CostWeights` | `mpc.config` | Nhóm weight cost. |
| `SafetyConfig` | `mpc.config` | Stale limit, state bounds, daily cap, fail-closed value. |
| `ControllerConfig` | `mpc.config` | Aggregate config V2/V3. |
| `AdaptiveConfig` | `mpc.config` | Bật/tắt bias adaptation, window residual, và giới hạn bias. |
| `ActuatorConfig` | `mpc.config` | Bật/tắt actuator, URL, env token name, và timeout HTTP. |
| `ControllerState` | `mpc.state` | `timestamp`, `soil_moisture`, disturbances, `last_pump_seconds`, optional `run_id`. |
| `DisturbanceForecast` | `mpc.state` | Forecast measured-hold cho `temperature`, `humidity`, `light`. |
| `Recommendation` | `mpc.types` | Output chính của `recommend`. |
| `SimulationReport` | `mpc.simulation` | Band violation, pump seconds, switching count, objective cost. |
| `BiasState` | `mpc.adaptive` | Bias correction window và current bias cho v3. |
| `ActuatorCommand` | `mpc.actuator` | Payload HTTP v3 sau safety gate. |

## 6. Validation Rules

- Reject config nếu `step_seconds <= 0`, `horizon_steps < 1`, `grid_seconds <= 0`, `grid_seconds > max_seconds`, hoặc `soft_daily_pump_cap_seconds <= 0`.
- Reject config nếu target band nằm ngoài `[0, 100]` hoặc `low >= high`.
- Reject config nếu `adaptive.enabled` không phải boolean, `adaptive.bias_window < 1`, hoặc `adaptive.max_abs_bias < 0`.
- Reject config nếu `actuator.enabled` không phải boolean, `actuator.url`/`actuator.bearer_token_env` không phải chuỗi khác rỗng hoặc `null`, hoặc `actuator.timeout_seconds <= 0`.
- Clamp pump command vào `[min_seconds, max_seconds]` tại safety boundary.
- Fail closed khi state thiếu, state không finite, timestamp stale, artifact/model lỗi, solver lỗi, hoặc actuator lỗi.
- Không hardcode actuator URL/token trong file config mẫu. V3 lấy token qua env name trong `bearer_token_env`.
