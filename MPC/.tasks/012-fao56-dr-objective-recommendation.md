---
id: "012"
title: "Switch MPC recommendation objective to FAO Dr/TAW/RAW control"
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
blocks: ["Green-House-003", "Green-House-006"]
blocked_by: ["011"]
---

## Description

Update MPC recommendation behavior so the primary control state is FAO root-zone depletion `Dr`, not legacy low/high sensor percent bands.

The solver should still return `predicted_soil_moisture` as sensor percent for current dashboard compatibility.

## Acceptance Criteria

- [x] Add a FAO mode or replace the current AMPC runtime objective so candidate pump sequences are evaluated using:
  - `stress_error = max(0, Dr_k - RAW)`
  - `overwater_error = max(0, -Dr_raw_next)`
  - `water_term = (u_k / pump_max_seconds)^2`
  - `switch_term = ((u_k - u_k-1) / pump_max_seconds)^2`
- [x] Stage cost uses:
  - `w_stress = cost_band_violation`
  - `w_overwater = cost_band_violation`
  - `w_water = cost_water`
  - `w_switch = cost_switching`
- [x] Terminal cost uses:
  - `w_terminal = cost_terminal_band_violation`
  - `terminal_cost = w_terminal * max(0, Dr_H - RAW)^2`
- [x] Use `overwater_error` from `Dr_raw_next` before clamping, so over-irrigation is penalized.
- [x] Do not hard reject all sequences with `Dr > RAW`; apply stress penalty and choose the least bad feasible sequence.
- [x] Enforce final state safety:
  - `0 <= Dr_k <= TAW`
  - fail closed on invalid FAO config, invalid ET0, invalid state, or non-finite prediction.
- [x] Recommendation output keeps existing fields:
  - `pump_seconds`
  - `step_seconds`
  - `predicted_soil_moisture`
  - `target_band`
  - `cost`
  - `safety_status`
  - `reason`
- [x] Recommendation output adds/audits FAO details through a backward-compatible field or state snapshot:
  - `initial_theta`
  - `initial_dr`
  - `taw`
  - `raw`
  - `ks`
  - `et0_step`
  - `etc_adj`
  - `irrigation_depth_mm`
  - predicted `Dr` series
- [x] CLI/demo defaults still run without requiring Django.
- [x] Tests prove wet profiles recommend zero or near-zero irrigation and dry/stressed profiles recommend non-zero irrigation when pump limits allow it.

## Completion Gates

- [x] Logic: Solver transition uses `Dr_next = clamp(Dr + ETc_adj - I, 0, TAW)` consistently across the horizon.
- [x] Nghiệp vụ: RAW acts as the stress threshold; dashboard percent output remains a display compatibility layer.
- [x] Security: Fail-closed behavior keeps pump seconds at `0` for invalid config/state/ET0 and does not bypass actuator safeguards.
- [x] Test chạy thực tế: `python -m pytest MPC\tests -q`, `python -m compileall -q MPC\mpc`, and relevant CLI smoke commands pass.

## Technical Notes

- Likely files:
  - `MPC/mpc/solver/grid.py`
  - `MPC/mpc/solver/cost.py`
  - `MPC/mpc/types.py`
  - `MPC/mpc/schema.py`
  - `MPC/tests/test_solver*.py`
  - `MPC/docs/technical/API.md`
  - `MPC/docs/technical/VALIDATION.md`
- Keep old output shape stable unless Green-House task #003 has been updated at the same time.
- Avoid changing actuator transport in this task.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-12 | Codex | Fixed review finding: simulation `objective_cost` now uses FAO `Dr/RAW` stress/overwater scoring instead of legacy sensor band scoring, with regression assertions for the exact formula. |
| 2026-05-12 | Codex | Switched grid solver objective to FAO `Dr/TAW/RAW`, added recommendation `fao56` audit details, updated tests/docs, and passed MPC gates plus CLI smoke commands. |
| 2026-05-12 | Codex | Task created from FAO-56 water-balance plan |
