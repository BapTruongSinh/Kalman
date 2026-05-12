# Plan: AMPC FAO-56 Water Balance With Capacitive Soil Sensor

Created: 2026-05-12
Status: proposed, ready for implementation
Scope: `Green-House` backend/frontend + `MPC` package

## 1. Goal

Replace the old AMPC low/high soil-moisture band logic with an FAO-56 style root-zone water balance model.

Important rule: the capacitive soil sensor percent is not volumetric water content.

`soil_moisture = 55%` means 55% on the calibrated sensor/app scale. It must not be treated as `theta = 0.55 m3/m3`.

The runtime control state should use:

- `theta`: estimated volumetric water content, `m3/m3`
- `Dr`: root-zone depletion, mm
- `TAW`: total available water, mm
- `RAW`: readily available water, mm
- `Ks`: water stress coefficient
- `ETc_adj`: adjusted crop evapotranspiration per control step, mm

The old `target_moisture_min` / `target_moisture_max` fields can remain for compatibility and display, but the FAO control path should use `Dr`, `TAW`, and `RAW`.

## 2. Greenhouse Config Inputs

Store these per `greenhouse_id` so backend auto mode and the MPC package read the same physical config.

Defaults:

```text
latitude = 16.0471
longitude = 108.2068
crop_kc = 1.0
soil_type = loam
theta_fc = 0.32
theta_wp = 0.15
theta_sat = 0.45
root_depth_m = 0.30
depletion_fraction_p = 0.5
pump_efficiency = 0.8
pump_flow_lps = 0.02
irrigation_area_m2 = 0.25
```

Soil presets:

| soil_type | theta_fc | theta_wp | theta_sat |
| --- | ---: | ---: | ---: |
| sand | 0.10 | 0.04 | 0.45 |
| light_loam | 0.15 | 0.06 | 0.45 |
| loam | 0.32 | 0.15 | 0.45 |
| clay_loam | 0.35 | 0.23 | 0.45 |

Validation:

```text
0 <= theta_wp < theta_fc < theta_sat <= 0.8
0 < root_depth_m
0 < depletion_fraction_p < 1
0 < pump_efficiency <= 1
pump_flow_lps > 0
irrigation_area_m2 > 0
```

## 3. ET0 Source And ETc

FAO-56 Penman-Monteith reference formula:

```text
ET0 =
  [0.408 * Delta * (Rn - G) + gamma * (900 / (T + 273)) * u2 * (es - ea)]
  / [Delta + gamma * (1 + 0.34 * u2)]
```

Implementation choice:

- Do not calculate the full Penman-Monteith formula locally in the first version.
- Fetch hourly `et0_fao_evapotranspiration` from Open-Meteo using the greenhouse coordinates.
- Cache ET0 hourly.
- If Open-Meteo fails, use a fresh recent cache.
- If there is no usable cache, fail closed: do not generate an automatic irrigation command.

Per MPC step:

```text
ET0_step = ET0_hour * step_seconds / 3600
ETc = Kc * ET0_step
```

Future full form:

```text
ETc = (Kcb + Ke) * ET0_step
```

First implementation uses the simplified form:

```text
ETc = Kc * ET0_step
Ke = 0
```

## 4. Capacitive Sensor Percent To Volumetric Water Content

Sensor percent:

```text
S = soil_moisture_sensor_percent
```

Use `theta_sat`, not `theta_fc`, as the wet end of the sensor scale:

```text
theta = theta_wp + (S / 100) * (theta_sat - theta_wp)
```

Reason:

```text
theta_wp < theta_fc < theta_sat
```

`theta_fc` is field capacity, not the maximum water content. A sensor can report values above the field-capacity equivalent after recent irrigation or saturated conditions.

Default loam example:

```text
S = 55
theta_wp = 0.15
theta_fc = 0.32
theta_sat = 0.45
root_depth_m = 0.30

theta = 0.15 + 0.55 * (0.45 - 0.15)
theta = 0.315
```

This is near field capacity, which is physically reasonable. The wrong conversion `theta = 0.55` would make the model think the soil is far wetter than field capacity.

For frontend charts and backward-compatible MPC output, convert predicted `theta` back to sensor percent:

```text
S_forecast = 100 * (theta - theta_wp) / (theta_sat - theta_wp)
S_forecast = clamp(S_forecast, 0, 100)
```

## 5. TAW, RAW, And Dr

Total available water:

```text
TAW = 1000 * (theta_fc - theta_wp) * root_depth_m
```

Readily available water:

```text
RAW = depletion_fraction_p * TAW
```

Raw depletion from current sensor-derived `theta`:

```text
Dr_raw = 1000 * (theta_fc - theta) * root_depth_m
```

Physical control state:

```text
Dr = clamp(Dr_raw, 0, TAW)
```

Meaning:

- `Dr < 0`: soil is wetter than field capacity. Clamp to `0`; do not irrigate more.
- `0 <= Dr <= RAW`: safe water zone, no crop stress.
- `RAW < Dr <= TAW`: crop starts water stress.
- `Dr > TAW`: soil is beyond wilting point. Clamp to `TAW` for model stability and treat as severe dry/stress.

Default loam example:

```text
TAW = 1000 * (0.32 - 0.15) * 0.30 = 51.0 mm
RAW = 0.5 * 51.0 = 25.5 mm
Dr_raw = 1000 * (0.32 - 0.315) * 0.30 = 1.5 mm
Dr = 1.5 mm
```

## 6. Water Stress Coefficient Ks

```text
if Dr <= RAW:
    Ks = 1
else:
    Ks = (TAW - Dr) / ((1 - depletion_fraction_p) * TAW)
```

Always clamp:

```text
Ks = clamp(Ks, 0, 1)
```

Adjusted crop evapotranspiration:

```text
ETc_adj = Ks * Kc * ET0_step
```

This is the simplified version of:

```text
ETc_adj = (Ks * Kcb + Ke) * ET0_step
```

with `Ke = 0` and `Kc` used as the frontend crop coefficient.

## 7. Irrigation Depth From Pump Runtime

MPC decision variable:

```text
u_k = pump on-time in seconds for step k
```

Irrigation depth:

```text
I_k(u_k) = (pump_efficiency * pump_flow_lps * u_k) / irrigation_area_m2
```

Units:

- `pump_flow_lps`: L/s
- `u_k`: s
- `irrigation_area_m2`: m2
- `1 L/m2 = 1 mm`

Example:

```text
pump_efficiency = 0.8
pump_flow_lps = 0.02
u_k = 300
irrigation_area_m2 = 0.25

I_k = 0.8 * 0.02 * 300 / 0.25 = 19.2 mm
```

## 8. Water Balance Dynamics

For each MPC prediction step:

```text
Dr_raw_next = Dr_k + ETc_adj_k - I_k(u_k)
Dr_k+1 = clamp(Dr_raw_next, 0, TAW)
```

Then convert back for charts and existing response fields:

```text
theta_k+1 = theta_fc - Dr_k+1 / (1000 * root_depth_m)
S_forecast_k+1 =
  100 * (theta_k+1 - theta_wp) / (theta_sat - theta_wp)
S_forecast_k+1 = clamp(S_forecast_k+1, 0, 100)
```

Safety constraint:

```text
0 <= Dr_k <= TAW
```

Do not accept prediction states outside this physical range as final model states.

## 9. MPC Objective

Use RAW as the stress threshold. Do not reject every sequence where `Dr > RAW`; instead apply a strong stress penalty so MPC can still choose the least bad action during very dry conditions.

Per-step terms:

```text
stress_error = max(0, Dr_k - RAW)
overwater_error = max(0, -Dr_raw_next)
water_term = (u_k / pump_max_seconds)^2
switch_term = ((u_k - u_k-1) / pump_max_seconds)^2
```

Stage cost:

```text
stage_cost =
  w_stress * stress_error^2
  + w_overwater * overwater_error^2
  + w_water * water_term
  + w_switch * switch_term
```

Terminal cost:

```text
terminal_cost = w_terminal * max(0, Dr_H - RAW)^2
```

First implementation can map to existing MPC cost fields to avoid expanding the UI more than needed:

```text
w_stress = cost_band_violation
w_overwater = cost_band_violation
w_terminal = cost_terminal_band_violation
w_water = cost_water
w_switch = cost_switching
```

`overwater_error` should use `Dr_raw_next` before clamping so the cost can penalize irrigation that would push the model wetter than field capacity.

## 10. Backend And Frontend Implementation Steps

1. Add FAO config fields to the greenhouse control profile model and migration.
2. Add API serializer/view support for the new fields.
3. Add frontend config controls:
   - crop coefficient `Kc`
   - soil type select box
   - root depth `Zr`
   - pump flow `Q`
   - irrigation area `A`
   - pump efficiency `eta`, default 0.8
4. When `soil_type` changes, populate `theta_fc`, `theta_wp`, and `theta_sat` from presets.
5. Add backend ET0 service:
   - Open-Meteo hourly fetch by greenhouse coordinates
   - hourly cache
   - fallback to recent cache
   - fail closed when no ET0 is available
6. Add a water-balance module in `MPC` for:
   - sensor percent to `theta`
   - `theta` to `Dr`
   - `TAW`, `RAW`
   - `Ks`
   - `ETc_adj`
   - irrigation depth
   - one-step water-balance transition
7. Update Green-House AMPC integration to pass FAO config and ET0 forecast/cache to MPC.
8. Return audit fields in recommendations:
   - `initial_theta`
   - `initial_dr`
   - `taw`
   - `raw`
   - `ks`
   - `et0_step`
   - `etc_adj`
   - `irrigation_depth_mm`
   - predicted `Dr` series
   - predicted sensor-percent moisture series
9. Keep old predicted soil-moisture percent output for current dashboard compatibility.
10. Update docs after code implementation:
    - `MPC/docs/technical/CONFIG.md`
    - `MPC/docs/technical/API.md`
    - `Green-House/docs/technical/AMPC_MODELING_HANDOFF.md`

## 11. Test Plan

Unit tests:

- Sensor conversion with loam defaults:
  - `S = 55`
  - `theta = 0.315`
  - `Dr = 1.5 mm`
- Boundary conversion:
  - `S = 100` gives `theta = 0.45`, `Dr = 0`
  - `S = 0` gives `theta = 0.15`, `Dr = TAW`
- TAW/RAW:
  - loam defaults give `TAW = 51.0 mm`
  - loam defaults give `RAW = 25.5 mm`
- Ks:
  - `Dr <= RAW` gives `Ks = 1`
  - `Dr = TAW` gives `Ks = 0`
- Irrigation depth:
  - `eta = 0.8`, `Q = 0.02 L/s`, `u = 300 s`, `A = 0.25 m2`
  - expected `I = 19.2 mm`
- Water balance:
  - dry state plus irrigation reduces `Dr`
  - wet state with excessive irrigation clamps `Dr` to `0` and penalizes overwater

Backend tests:

- Save/load FAO config per greenhouse.
- Soil preset updates physical soil fields.
- Users cannot update another user's greenhouse FAO config.
- ET0 service uses Open-Meteo response when available.
- ET0 service uses recent cache on network/API failure.
- ET0 service fails closed when no cache exists.

Integration tests:

- Dry profile should recommend non-zero irrigation when `Dr > RAW`.
- Wet profile should recommend zero irrigation when `Dr = 0`.
- Returned recommendation includes FAO audit fields and existing dashboard fields.

## 12. Risks And Notes

- The sensor-percent to `theta` mapping is still an approximation. Real calibration should use measured dry/wet references for each soil/sensor installation.
- Historical moisture data in the old 0-100 scale remains usable for display, but physical interpretation starts only after this mapping is introduced.
- Open-Meteo becomes part of the auto-control dependency path, so caching and fail-closed behavior are required.
- The first version intentionally ignores `Ke` and separate `Kcb`; the frontend `Kc` is the single crop coefficient.

## 13. Acceptance Criteria

- The plan above is the source of truth for implementing FAO-56 AMPC water balance.
- Formula tests pass with the numeric examples in this file.
- Auto mode no longer compares capacitive sensor percent directly against physical `theta_fc`.
- MPC decisions are based on `Dr`, `TAW`, `RAW`, `Ks`, `ETc_adj`, and pump irrigation depth.
- Dashboard compatibility remains by exposing predicted moisture as sensor percent.

## 14. Task Mapping

MPC package tasks:

- `MPC/.tasks/011-fao56-water-balance-model.md`: pure FAO config/contracts/formula module and unit tests.
- `MPC/.tasks/012-fao56-dr-objective-recommendation.md`: solver objective, recommendation output, fail-closed behavior, and CLI/API compatibility.

Green-House runtime tasks:

- `Green-House/.tasks/001-fao56-control-profile-config.md`: per-greenhouse DB/API config fields and validation.
- `Green-House/.tasks/002-open-meteo-et0-service.md`: hourly Open-Meteo ET0 fetch/cache/fail-closed service.
- `Green-House/.tasks/003-wire-ampc-fao-runtime.md`: backend AMPC integration from profile + ET0 + MPC to persisted recommendation/audit.
- `Green-House/.tasks/004-fao-auto-settings-frontend.md`: frontend config controls and soil preset UI.
- `Green-House/.tasks/005-fao-forecast-audit-ui.md`: forecast/dashboard audit display while keeping percent chart compatibility.
- `Green-House/.tasks/006-fao-integration-gates-docs.md`: final integration gates and docs update after implementation is accepted.
