# AMPC Modeling Handoff

> Active integration target: `Green-House/`.
> Algorithm packages: `Kalman/` and `MPC/`.
> ARX artifact: `ARX/arx_model.json`.

## Current Production Shape

Green-House runs AMPC by composing existing packages:

- Kalman package validates/preprocesses live readings and produces filtered soil moisture.
- ET0 service fetches hourly Open-Meteo `et0_fao_evapotranspiration` by greenhouse coordinates and falls back to fresh cache.
- MPC package loads the ARX artifact as plant model and computes pump recommendations with FAO-56 root-zone depletion.
- Green-House persists both estimation cycles and AMPC audit rows in MySQL.

The active state/control contract is:

- state: selected sensor-percent soil moisture from `EstimationCycle.kf_x_posterior`, falling back to raw moisture when Kalman trust is low
- physical control state: MPC maps sensor percent to `theta`, `Dr`, `TAW`, `RAW`, `Ks`, `ETc_adj`, and irrigation depth
- exogenous inputs: temperature, humidity, light
- actuator/control input: pump seconds per MPC step
- output: `AMPCRecommendation` with safety status, reason, sensor-percent forecast, FAO audit snapshot, cost, and optional queued pump command

## Safety Contract

AMPC must fail closed when:

- ARX artifact is missing or invalid
- latest sample is stale or future-dated beyond skew tolerance
- solver/model raises
- Open-Meteo ET0 is unavailable and no valid cached ET0 exists
- latest state/history is not valid enough for prediction
- actuator is disabled, unconfigured, or recommendation is not safe

Fail closed means:

- pump seconds are `0`
- safety status is not `safe`
- no dangerous actuator command is queued
- audit row is still saved for dashboard/debugging

## Ownership Contract

All production AMPC API routes are greenhouse-scoped:

```text
authenticated user
  -> Greenhouse.owner
  -> GreenhouseControlProfile
  -> EstimationCycle history
  -> AMPCRecommendation
```

An authenticated user must not run or read AMPC data for another user's greenhouse.

## FAO-56 Control Contract

The automatic irrigation decision no longer uses the legacy low/high sensor-percent band as the control objective. The selected sensor percent remains a dashboard-compatible input/output, but MPC converts it first:

```text
theta = theta_wp + (S / 100) * (theta_sat - theta_wp)
TAW = 1000 * (theta_fc - theta_wp) * root_depth_m
RAW = depletion_fraction_p * TAW
Dr = clamp(1000 * (theta_fc - theta) * root_depth_m, 0, TAW)
Ks = 1 when Dr <= RAW, else clamp((TAW - Dr) / ((1 - p) * TAW), 0, 1)
ET0_step = ET0_hour * step_seconds / 3600
ETc_adj = Ks * crop_kc * ET0_step
I = pump_efficiency * pump_flow_lps * pump_seconds / irrigation_area_m2
Dr_next = clamp(Dr + ETc_adj - I, 0, TAW)
```

The MPC objective penalizes stress `max(0, Dr - RAW)`, overwater before clamping `max(0, -Dr_raw_next)`, water use, switching, soft daily cap, and terminal stress.

`AMPCRecommendation.state_snapshot.fao56` stores `initial_theta`, `initial_dr`, `taw`, `raw`, `ks`, `et0_step`, `etc_adj`, `irrigation_depth_mm`, predicted `Dr`, and predicted sensor-percent moisture. `state_snapshot.et0` stores the ET0 source or fail-closed reason.

## Frontend Settings Contract

`Green-House/frontend/src/app/components/AutoSettings.tsx` exposes the persisted FAO-56 profile through the legacy `/api/auto-settings/` endpoint.

The form sends the backend field names directly for `crop_kc`, `soil_type`, `theta_fc`, `theta_wp`, `theta_sat`, `root_depth_m`, `depletion_fraction_p`, `pump_efficiency`, `pump_flow_lps`, `irrigation_area_m2`, `latitude`, and `longitude`.

Soil presets in the frontend match the accepted backend/MPC contract:

| soil_type | theta_fc | theta_wp | theta_sat |
| --- | ---: | ---: | ---: |
| `sand` | 0.10 | 0.04 | 0.45 |
| `light_loam` | 0.15 | 0.06 | 0.45 |
| `loam` | 0.32 | 0.15 | 0.45 |
| `clay_loam` | 0.35 | 0.23 | 0.45 |

Selecting a soil preset fills the theta fields on the client, but users can still edit those physical values before saving. The UI labels keep sensor-percent thresholds separate from volumetric `theta` values.

## Frontend Forecast Contract

`Green-House/frontend/src/app/components/ForecastPage.tsx` keeps the forecast chart on `AMPCRecommendation.predicted_soil_moisture`, which is still sensor percent for dashboard compatibility.

The same page renders `AMPCRecommendation.state_snapshot.fao56` as optional diagnostics. It shows `Dr`, `TAW`, `RAW`, `Ks`, `ET0_step`, `ETc_adj`, and `irrigation_depth_mm` without converting those values into sensor percent. It classifies the current FAO state as:

- wet/no-irrigation when `Dr = 0`
- safe zone when `Dr <= RAW`
- water stress when `Dr > RAW`

Older recommendation responses that do not have `state_snapshot.fao56` still render the percent chart and show null-safe placeholders in the audit panel. Frontend error text normalizes backend reasons and does not display raw stack traces or file paths.

## Implementation Files

- `Green-House/backend/api/estimation.py`: SensorData -> `api_estimationcycle`
- `Green-House/backend/api/ampc.py`: greenhouse-scoped AMPC service
- `Green-House/backend/api/views.py`: REST endpoints
- `Green-House/backend/api/models.py`: greenhouse, config, estimation, recommendation models
- `Green-House/frontend/src/app/components/AutoSettings.tsx`: FAO profile controls and legacy dashboard settings
- `Green-House/frontend/src/app/components/ForecastPage.tsx`: percent forecast chart and FAO audit diagnostics
- `MPC/mpc/solver/`: grid shooting solver
- `MPC/mpc/plant/arx.py`: ARX plant model
- `MPC/mpc/config.py`: controller config and cost weights
