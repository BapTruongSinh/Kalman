# AMPC Modeling Handoff

> Active integration target: `Green-House/`.
> Algorithm packages: `Kalman/` and `MPC/`.
> ARX artifact: `ARX/arx_model.json`.

## Current Production Shape

Green-House runs AMPC by composing existing packages:

- Kalman package validates/preprocesses live readings and produces filtered soil moisture.
- MPC package loads the ARX artifact as plant model and computes pump recommendations.
- Green-House persists both estimation cycles and AMPC audit rows in MySQL.

The active state/control contract is:

- state: soil moisture from `EstimationCycle.kf_x_posterior`, falling back to raw moisture when needed
- exogenous inputs: temperature, humidity, light
- actuator/control input: pump seconds per MPC step
- output: `AMPCRecommendation` with safety status, reason, forecast, cost, and optional queued pump command

## Safety Contract

AMPC must fail closed when:

- ARX artifact is missing or invalid
- latest sample is stale or future-dated beyond skew tolerance
- solver/model raises
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

## Cost Contract

The MPC objective uses normalized terms:

```text
sum over horizon:
  w_band * band_error^2
  w_water * (pump_seconds / max_pump_seconds)^2
  w_switch * ((pump_seconds - previous_pump_seconds) / max_pump_seconds)^2
plus:
  w_daily * daily_excess_ratio^2
  w_terminal * terminal_band_error^2
```

Band error is zero inside `[target_low, target_high]` and positive distance outside the band.

## Implementation Files

- `Green-House/backend/api/estimation.py`: SensorData -> `api_estimationcycle`
- `Green-House/backend/api/ampc.py`: greenhouse-scoped AMPC service
- `Green-House/backend/api/views.py`: REST endpoints
- `Green-House/backend/api/models.py`: greenhouse, config, estimation, recommendation models
- `MPC/mpc/solver/`: grid shooting solver
- `MPC/mpc/plant/arx.py`: ARX plant model
- `MPC/mpc/config.py`: controller config and cost weights
