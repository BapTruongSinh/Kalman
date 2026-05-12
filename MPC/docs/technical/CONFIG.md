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
| `fao56.soil_type` | `loam` | Soil preset default for FAO-56 water-balance primitives. |
| `fao56.theta_fc/wp/sat` | `0.32 / 0.15 / 0.45` | Loam field-capacity, wilting-point, and first-version default wet-end sensor mapping. |
| `fao56.root_depth_m` | `0.3` | Effective root depth for converting volumetric water content to mm. |
| `fao56.depletion_fraction_p` | `0.5` | Readily available water fraction. |
| `fao56.et0_hour_mm` | `0.6` | Default hourly FAO ET0 for CLI/demo runs; Green-House integration can override it from Open-Meteo. |
| `fao56.pump_efficiency/flow/area` | `0.8 / 0.02 / 0.25` | Defaults for delivered irrigation depth in mm. |
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

The grid solver evaluates pump candidates with FAO-56 root-zone depletion as the primary control state:

```text
stress_error_i = max(0, Dr_i - RAW)
overwater_error_i = max(0, -Dr_raw_next_i)
water_term_i = (pump_seconds_i / pump.max_seconds)^2
switch_term_i = ((pump_seconds_i - pump_seconds_{i-1}) / pump.max_seconds)^2

stage_cost_i =
  band_violation * stress_error_i^2
  + band_violation * overwater_error_i^2
  + water_use * water_term_i
  + switching * switch_term_i

daily_excess_ratio =
  max(0, used_today + sum(pump_seconds_i) - soft_daily_cap) / soft_daily_cap

daily_cap_cost = daily_cap_excess * daily_excess_ratio^2
terminal_cost = terminal_band_violation * max(0, Dr_H - RAW)^2

total_cost = sum(stage_cost_i) + daily_cap_cost + terminal_cost
```

Notes:

- `RAW` is the stress threshold; sequences with `Dr > RAW` are penalized, not hard rejected.
- `overwater_error_i` is computed from `Dr_raw_next_i` before clamping, so over-irrigation is visible to the objective.
- Water and switching normalize by `pump.max_seconds`, not `step_seconds`.
- `predicted_soil_moisture` remains sensor percent for dashboard compatibility, but the objective is Dr/TAW/RAW.

## 3.1 Legacy Band Cost Reference

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

## 4.1 FAO-56 Water Balance

`mpc.fao56.Fao56Config` is a pure Python contract with no Django, database, HTTP, Open-Meteo, or secret dependency. The capacitive sensor percent is never compared directly with `theta_fc`; it is first mapped to volumetric water content:

```text
theta = theta_wp + (S / 100) * (theta_sat - theta_wp)
S_forecast = 100 * (theta - theta_wp) / (theta_sat - theta_wp)
```

Soil presets:

| `soil_type` | `theta_fc` | `theta_wp` | `theta_sat` |
|-------------|------------|------------|-------------|
| `sand` | `0.10` | `0.04` | `0.45` |
| `light_loam` | `0.15` | `0.06` | `0.45` |
| `loam` | `0.32` | `0.15` | `0.45` |
| `clay_loam` | `0.35` | `0.23` | `0.45` |

`theta_sat=0.45` is the first-version default wet-end mapping for the sensor scale.

Core formulas:

```text
TAW = 1000 * (theta_fc - theta_wp) * root_depth_m
RAW = depletion_fraction_p * TAW
Dr_raw = 1000 * (theta_fc - theta) * root_depth_m
Dr = clamp(Dr_raw, 0, TAW)
Ks = 1 when Dr <= RAW, else (TAW - Dr) / ((1 - p) * TAW)
ET0_step = ET0_hour * step_seconds / 3600
ETc_adj = Ks * Kc * ET0_step
I_k(u_k) = (eta * Q * u_k) / A
Dr_raw_next = Dr_k + ETc_adj_k - I_k(u_k)
Dr_next = clamp(Dr_raw_next, 0, TAW)
```

## 4.2 Green-House Runtime Mapping

Green-House runtime không đọc trực tiếp JSON config của CLI. Django lưu cấu hình theo từng `GreenhouseControlProfile`, sau đó `Green-House/backend/api/ampc.py::profile_to_config()` dựng `ControllerConfig` cho MPC.

| Green-House field | MPC config field |
|-------------------|------------------|
| `crop_kc` | `fao56.crop_kc` |
| `soil_type` | `fao56.soil_type` |
| `theta_fc` / `theta_wp` / `theta_sat` | `fao56.theta_fc/wp/sat` |
| `root_depth_m` | `fao56.root_depth_m` |
| `depletion_fraction_p` | `fao56.depletion_fraction_p` |
| Open-Meteo ET0 service output | `fao56.et0_hour_mm` |
| `pump_efficiency` / `pump_flow_lps` / `irrigation_area_m2` | `fao56.pump_efficiency/flow/area` |
| `target_low` / `target_high` | `target_band.low/high` |
| `cost_*` fields | `cost.*` weights |
| `safety_stale_after_seconds` / `soft_daily_pump_cap_seconds` | `safety.*` |
| `adaptive_*` fields | `adaptive.*` |

Nếu persisted profile trong DB không hợp lệ, Green-House không gọi ET0 hoặc solver. Runtime tạo audit `AMPCRecommendation` fail-closed với `safety_status="config_error"` và `pump_seconds=0`.

## 5. Public Dataclasses

| Dataclass | Module | Purpose |
|-----------|--------|---------|
| `TargetBand` | `mpc.config` | `low`, `high` và validate `0 <= low < high <= 100`. |
| `PumpLimits` | `mpc.config` | `min_seconds`, `max_seconds`, `grid_seconds`; sinh candidate grid. |
| `CostWeights` | `mpc.config` | Nhóm weight cost. |
| `SafetyConfig` | `mpc.config` | Stale limit, state bounds, daily cap, fail-closed value. |
| `Fao56Config` | `mpc.fao56` | Soil/crop/hydraulic parameters for FAO-56 water balance. |
| `Fao56State` | `mpc.fao56` | Sensor percent mapped to theta, TAW, RAW, Dr, and Ks. |
| `Fao56Step` | `mpc.fao56` | One-step depletion transition with ET, irrigation, and clamped next Dr. |
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

- Reject FAO-56 config if any numeric field is non-finite or if it violates `0 <= theta_wp < theta_fc < theta_sat <= 0.8`, `root_depth_m > 0`, `0 < depletion_fraction_p < 1`, `et0_hour_mm >= 0`, `0 < pump_efficiency <= 1`, `pump_flow_lps > 0`, or `irrigation_area_m2 > 0`.

- Reject config nếu `step_seconds <= 0`, `horizon_steps < 1`, `grid_seconds <= 0`, `grid_seconds > max_seconds`, hoặc `soft_daily_pump_cap_seconds <= 0`.
- Reject config nếu target band nằm ngoài `[0, 100]` hoặc `low >= high`.
- Reject config nếu `adaptive.enabled` không phải boolean, `adaptive.bias_window < 1`, hoặc `adaptive.max_abs_bias < 0`.
- Reject config nếu `actuator.enabled` không phải boolean, `actuator.url`/`actuator.bearer_token_env` không phải chuỗi khác rỗng hoặc `null`, hoặc `actuator.timeout_seconds <= 0`.
- Clamp pump command vào `[min_seconds, max_seconds]` tại safety boundary.
- Fail closed khi state thiếu, state không finite, timestamp stale, artifact/model lỗi, solver lỗi, hoặc actuator lỗi.
- Không hardcode actuator URL/token trong file config mẫu. V3 lấy token qua env name trong `bearer_token_env`.
