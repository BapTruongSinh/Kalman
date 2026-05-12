---
id: "003"
title: "Wire Green-House AMPC runtime to FAO MPC water-balance mode"
status: "completed"
area: "backend"
agent: "@builder"
required_skills: ["backend", "quality", "backend-security-coder", "docs"]
priority: "high"
created_at: "2026-05-12"
due_date: null
started_at: "2026-05-12"
completed_at: "2026-05-12"
prd_refs: []
blocks: ["005", "006"]
blocked_by: ["001", "002", "MPC-011", "MPC-012"]
---

## Description

Connect Green-House AMPC runtime to the FAO water-balance logic from MPC.

`run_auto_recommendation()` should build FAO config from `GreenhouseControlProfile`, obtain ET0, pass sensor-derived state to MPC, persist FAO audit fields, and still return existing dashboard-compatible predicted moisture percent.

## Acceptance Criteria

- [x] Update `profile_to_config()` or a new adapter to include FAO config fields from `GreenhouseControlProfile`.
- [x] Keep `crop_kc` as the crop coefficient used by `ETc_adj = Ks * Kc * ET0_step`.
- [x] Use the selected control soil moisture percent `S` from the existing raw/Kalman trust logic, then let MPC convert `S -> theta -> Dr`.
- [x] Call the ET0 service from task #002 before solving.
- [x] If ET0 is unavailable and no cache is valid, persist an AMPC recommendation/audit with:
  - pump seconds `0`
  - fail-closed safety status
  - reason indicating ET0 unavailable
  - no actuator command queued
- [x] Persist FAO audit data in `AMPCRecommendation.state_snapshot` or explicit fields:
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
- [x] Preserve existing fields used by current FE:
  - `pump_seconds`
  - `step_seconds`
  - `predicted_soil_moisture`
  - `target_band`
  - `objective_cost`
  - `safety_status`
  - `reason`
  - `bias_correction`
  - `bias_window_count`
- [x] Keep actuator fail-safe invariant:
  - only queue pump command when control mode is `AUTO`
  - actuator enabled
  - recommendation safety is `safe`
  - pump command is non-dangerous
- [x] Tests cover:
  - wet state `Dr=0` leads to zero pump
  - dry/stressed state `Dr>RAW` leads to non-zero pump when possible
  - ET0 unavailable fails closed and queues no command
  - audit fields are present
  - greenhouse ownership scoping remains intact

## Completion Gates

- [x] Logic: Runtime flow is `sensor percent -> theta -> Dr -> TAW/RAW/Ks/ETc_adj -> MPC -> percent forecast`.
- [x] Nghiệp vụ: Legacy low/high percent no longer drives automatic irrigation decisions.
- [x] Security: Ownership checks and actuator fail-closed behavior remain intact.
- [x] Test chạy thực tế: `cd Green-House\backend; python manage.py test api`, `python manage.py check`, and `python -m pytest MPC\tests -q` pass.

## Technical Notes

- Relevant files:
  - `Green-House/backend/api/ampc.py`
  - `Green-House/backend/api/ampc_scheduler.py`
  - `Green-House/backend/api/models.py`
  - `Green-House/backend/api/serializers.py`
  - `Green-House/backend/api/tests/test_server_cutover.py`
  - MPC solver/config modules from tasks #011/#012
- This is the critical path task. Do not start until Green-House #001/#002 and MPC #011/#012 are done.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-12 | Codex | Fixed review finding: invalid FAO profile values already in DB now persist a `config_error` fail-closed audit with pump `0`, skip ET0/solver, and queue no actuator command. |
| 2026-05-12 | Codex | Wired AMPC runtime to profile FAO config plus Open-Meteo ET0, persisted FAO/ET0 audit in `state_snapshot`, kept legacy response fields, added fail-closed ET0 tests, and passed backend/MPC gates. |
| 2026-05-12 | Codex | Task created from FAO-56 AMPC plan |
