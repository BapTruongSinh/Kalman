# MPC Architecture

> Owner: @planner
> Update trigger: thay đổi package boundary, solver interface, actuator safety, hoặc integration với Kalman.

## 1. Scope

`MPC/` là controller project tách khỏi `Kalman/`. `Kalman/` cung cấp state estimation; `ARX/` cung cấp model artifact; `MPC/` quyết định lệnh bơm.

```text
Kalman posterior/raw state
  -> MPC state adapter
  -> ARX plant model adapter
  -> grid-shooting MPC solver
  -> recommendation JSON
  -> v3 optional HTTP actuator adapter
```

## 2. Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python | Khớp backend/ARX, dễ test và CLI |
| Runtime | Package + CLI | Độc lập Django, dễ chạy simulation |
| Model | ARX artifact JSON | Reuse mô hình hiện có, không train lại trong v2 |
| Solver | Grid shooting | Phù hợp SISO pump, không thêm dependency nặng |
| Adaptation | Bias correction | Ít rủi ro hơn RLS online ở bước đầu |
| Actuator | HTTP POST + Bearer | Dễ fake test và tích hợp thiết bị |

## 3. Planned Modules

| Module | Responsibility |
|--------|----------------|
| `mpc.config` | Load/validate controller config |
| `mpc.state` | State/history contracts, Kalman posterior fallback raw |
| `mpc.plant.arx` | Load ARX artifact, forecast soil moisture |
| `mpc.solver.grid` | Grid-shooting optimizer |
| `mpc.simulation` | Offline simulation and baseline comparison |
| `mpc.adaptive` | Bias estimator and AMPC wrapper |
| `mpc.actuator.http` | HTTP command adapter and fail-safe |
| `mpc.closed_loop` | Closed-loop service that combines solver, safety, and actuator result |
| `mpc.cli` | `simulate`, `recommend`, `adaptive-simulate`, `closed-loop`, `auto`, `config-schema` |

## 3.1 Package Layout Chốt Cho V2/V3

```text
MPC/
  pyproject.toml
  mpc/
    __init__.py
    cli.py
    config.py
    types.py
    state.py
    safety.py
    plant/
      __init__.py
      base.py
      arx.py
    solver/
      __init__.py
      grid.py
      cost.py
    simulation/
      __init__.py
      baseline.py
      runner.py
      report.py
    adaptive/
      __init__.py
      bias.py
    actuator/
      __init__.py
      base.py
      http.py
  tests/
    test_config.py
    test_state.py
    test_arx_plant.py
    test_grid_solver.py
    test_simulation.py
    test_safety.py
```

Boundary rules:

- `mpc.config`, `mpc.types`, `mpc.state`, và `mpc.safety` là core module ít dependency.
- `mpc.plant.arx` được đọc `../ARX/arx_model.json`, nhưng không import notebook hoặc training code của `ARX/`.
- `mpc.solver.grid` chỉ phụ thuộc plant interface và config; không biết CLI, HTTP, Django, hoặc file path.
- `mpc.simulation` được đọc CSV/JSON fixture và so sánh threshold baseline, nhưng v2 không ghi DB.
- `mpc.actuator.http` chỉ thuộc v3 và nằm sau adapter để fake actuator test thay thế được.
- `mpc.closed_loop` không biết token thô trong output; token chỉ đi từ env vào HTTP header.

## 3.2 Public Contracts

Implementation ban đầu nên expose frozen dataclasses từ `mpc.config`, `mpc.state`, và `mpc.types`:

- `ControllerConfig`, `TargetBand`, `PumpLimits`, `CostWeights`, `SafetyConfig`.
- `ControllerState` ưu tiên `kf_x_posterior` trước `raw_soil_moisture`.
- `DisturbanceForecast` dùng measured-hold `Temperature`, `Humidity`, `Light`.
- `Recommendation` gồm `pump_seconds`, `step_seconds`, `predicted_soil_moisture`, `target_band`, `cost`, `safety_status`, và `reason`.

Schema config chi tiết nằm ở [`CONFIG.md`](./CONFIG.md).

## 4. Data Flow

V2 recommendation:

```text
state_json + config + arx_model.json
  -> validate state freshness and bounds
  -> build measured-hold disturbance forecast
  -> enumerate pump candidates: 0, 30, ..., 300 seconds
  -> forecast horizon using ARX
  -> score cost
  -> return first pump_seconds + predicted trajectory summary
```

V3 closed-loop:

```text
state source
  -> AMPC bias correction
  -> MPC recommendation
  -> safety gate
  -> HTTP POST command if config explicit
  -> pump off + alert/log otherwise
```

## 5. Safety Boundary

- Pump command always clamped to `[0, 300]`.
- Stale sample limit: 10 phút.
- Missing state/model/solver/HTTP failure: pump off.
- Bearer token and actuator URL never committed.
- Fake actuator tests required before real pilot.
- Auto execute only runs when `actuator.enabled=true`, URL exists, token env name exists, and the env token is present.

## 6. CLI Layout

| Command | Phase | Input | Output |
|---------|-------|-------|--------|
| `python -m mpc recommend` | V2 | state JSON, optional history JSON, config, ARX artifact | recommendation JSON |
| `python -m mpc simulate` | V2 | CSV trace, config, ARX artifact | simulation report JSON |
| `python -m mpc adaptive-simulate` | V3 | same as simulate plus residual window | comparison report JSON with `mpc`, `ampc`, `threshold` |
| `python -m mpc closed-loop` | V3 | state source, config, actuator config | HTTP command hoặc pump-off fail-safe |
| `python -m mpc auto` | V3 | same as closed-loop, with default demo paths when omitted | HTTP command hoặc pump-off fail-safe |
| `python -m mpc config-schema` | V2/V3 | none | website-loadable defaults and field groups |

V2 commands phải chạy không cần Django, database, SciPy, hoặc CVXPY.
