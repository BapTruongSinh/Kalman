---
id: "011"
title: "Add FAO-56 water-balance model and config contracts"
status: "completed"
area: "backend"
agent: "@builder"
required_skills: ["backend", "quality", "docs", "planning"]
priority: "high"
created_at: "2026-05-12"
due_date: null
started_at: "2026-05-12"
completed_at: "2026-05-12"
prd_refs: []
blocks: ["012", "Green-House-003"]
blocked_by: []
---

## Description

Implement the pure MPC FAO-56 water-balance primitives from `Green-House/docs/plan/2026-05-12-fao-56-ampc-water-balance.md`.

This task does not wire Green-House runtime yet. It creates the reusable package layer that both CLI tests and Django integration can call.

## Acceptance Criteria

- [x] Add FAO config/data contracts for soil/crop/hydraulic parameters:
  - `crop_kc`
  - `soil_type`
  - `theta_fc`
  - `theta_wp`
  - `theta_sat`
  - `root_depth_m`
  - `depletion_fraction_p`
  - `pump_efficiency`
  - `pump_flow_lps`
  - `irrigation_area_m2`
- [x] Add soil presets:
  - `sand`: `theta_fc=0.10`, `theta_wp=0.04`, `theta_sat=0.45`
  - `light_loam`: `theta_fc=0.15`, `theta_wp=0.06`, `theta_sat=0.45`
  - `loam`: `theta_fc=0.32`, `theta_wp=0.15`, `theta_sat=0.45`
  - `clay_loam`: `theta_fc=0.35`, `theta_wp=0.23`, `theta_sat=0.45`
- [x] Validate physical config:
  - `0 <= theta_wp < theta_fc < theta_sat <= 0.8`
  - `root_depth_m > 0`
  - `0 < depletion_fraction_p < 1`
  - `0 < pump_efficiency <= 1`
  - `pump_flow_lps > 0`
  - `irrigation_area_m2 > 0`
- [x] Add formula functions:
  - `theta = theta_wp + (S / 100) * (theta_sat - theta_wp)`
  - `S_forecast = 100 * (theta - theta_wp) / (theta_sat - theta_wp)`
  - `TAW = 1000 * (theta_fc - theta_wp) * root_depth_m`
  - `RAW = depletion_fraction_p * TAW`
  - `Dr_raw = 1000 * (theta_fc - theta) * root_depth_m`
  - `Dr = clamp(Dr_raw, 0, TAW)`
  - `Ks = 1` when `Dr <= RAW`, else `(TAW - Dr) / ((1 - p) * TAW)`
  - `ET0_step = ET0_hour * step_seconds / 3600`
  - `ETc_adj = Ks * Kc * ET0_step`
  - `I_k(u_k) = (eta * Q * u_k) / A`
  - `Dr_raw_next = Dr_k + ETc_adj_k - I_k(u_k)`
  - `Dr_next = clamp(Dr_raw_next, 0, TAW)`
- [x] Preserve sensor semantics: sensor percent is never treated as direct volumetric `theta`.
- [x] Unit tests cover numeric examples from the plan:
  - loam defaults + `S=55` gives `theta=0.315`, `TAW=51.0`, `RAW=25.5`, `Dr=1.5`
  - `S=100` gives `theta=0.45`, `Dr=0`
  - `S=0` gives `theta=0.15`, `Dr=TAW`
  - `Dr<=RAW` gives `Ks=1`, `Dr=TAW` gives `Ks=0`
  - `eta=0.8`, `Q=0.02`, `u=300`, `A=0.25` gives `I=19.2 mm`
- [x] Public docs mention that `theta_sat=0.45` is the first-version default wet-end mapping.

## Completion Gates

- [x] Logic: All formulas match the accepted FAO plan and unit conversions are dimensionally consistent.
- [x] Nghiệp vụ: Capacitive sensor percent is mapped through `theta_wp/theta_sat`, not compared directly with `theta_fc`.
- [x] Security: Config loading rejects invalid/non-finite values and does not introduce secrets or external calls.
- [x] Test chạy thực tế: `python -m pytest MPC\tests -q` and `python -m compileall -q MPC\mpc` pass.

## Technical Notes

- Prefer a small pure module such as `MPC/mpc/water_balance.py` or `MPC/mpc/fao56.py`.
- Keep the module independent from Django, database, and Open-Meteo.
- This task can update `MPC/mpc/config.py`, `MPC/mpc/schema.py`, `MPC/mpc/__init__.py`, and `MPC/docs/technical/CONFIG.md` if needed.
- Do not remove the old target-band path in this task; task #012 performs solver integration.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-12 | Codex | Task created from FAO-56 water-balance plan |
| 2026-05-12 | Codex | Implemented pure `mpc.fao56` contracts/formulas, config/schema docs, and unit coverage; MPC tests and compileall passed. |
