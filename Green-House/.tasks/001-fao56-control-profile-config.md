---
id: "001"
title: "Add FAO-56 physical config to greenhouse control profile"
status: "completed"
area: "database"
agent: "@builder"
required_skills: ["database", "backend", "quality", "docs"]
priority: "high"
created_at: "2026-05-12"
due_date: null
started_at: "2026-05-12"
completed_at: "2026-05-12"
prd_refs: []
blocks: ["003", "004", "006"]
blocked_by: []
---

## Description

Add per-greenhouse FAO-56 physical configuration to `GreenhouseControlProfile` so backend AMPC, MPC package integration, and frontend settings use the same values.

This task only adds persistent config/API support. It does not change the solver behavior yet.

## Acceptance Criteria

- [x] Add model fields to `Green-House/backend/api/models.py` for:
  - `latitude`, default `16.0471`
  - `longitude`, default `108.2068`
  - `soil_type`, default `loam`
  - `theta_fc`, default `0.32`
  - `theta_wp`, default `0.15`
  - `theta_sat`, default `0.45`
  - `root_depth_m`, default `0.30`
  - `depletion_fraction_p`, default `0.5`
  - `pump_efficiency`, default `0.8`
  - `pump_flow_lps`, default `0.02`
  - `irrigation_area_m2`, default `0.25`
- [x] Preserve existing fields such as `crop_kc`, `target_moisture_min`, `target_moisture_max`, pump bounds, adaptive config, and actuator config.
- [x] Add a reversible Django migration with additive columns only.
- [x] Update serializers:
  - `GreenhouseControlProfileSerializer`
  - legacy `/api/auto-settings/` response mapping if it uses explicit field lists
- [x] Add backend validation:
  - `0 <= theta_wp < theta_fc < theta_sat <= 0.8`
  - `root_depth_m > 0`
  - `0 < depletion_fraction_p < 1`
  - `0 < pump_efficiency <= 1`
  - `pump_flow_lps > 0`
  - `irrigation_area_m2 > 0`
  - valid `soil_type` from preset list
- [x] Soil preset behavior is defined in one place and can populate `theta_fc/theta_wp/theta_sat`.
- [x] Tests cover:
  - save/load FAO fields through `/api/auto-settings/`
  - save/load FAO fields through `/api/greenhouses/<id>/control-profile/`
  - invalid physical ordering is rejected
  - another user's greenhouse config cannot be updated

## Completion Gates

- [x] Logic: Config fields are stored once per greenhouse and map cleanly to MPC config later.
- [x] Nghiep vu: Defaults match the accepted plan: Da Nang coordinates, loam, `theta_sat=0.45`, `p=0.5`, `Zr=0.30`.
- [x] Security: Ownership checks remain enforced through `Greenhouse.owner`; API rejects invalid input instead of silently correcting dangerous values.
- [x] Test chay thuc te: `cd Green-House\backend; python manage.py test api`, `python manage.py check`, and `python manage.py makemigrations --check --dry-run` pass.

## Technical Notes

- Relevant files:
  - `Green-House/backend/api/models.py`
  - `Green-House/backend/api/serializers.py`
  - `Green-House/backend/api/views.py`
  - `Green-House/backend/api/tests/test_server_cutover.py`
  - `Green-House/backend/api/migrations/0010_add_fao56_control_profile_config.py`
- Use additive migration. Do not remove old low/high target fields in this task.
- Keep `crop_kc` as the user-entered crop coefficient for `ETc = Kc * ET0_step`.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-12 | Codex | Task created from FAO-56 AMPC plan |
| 2026-05-12 | Codex | Implemented additive FAO-56 physical config fields, soil presets, serializer validation, legacy auto-settings mapping, API type update, migration, and backend tests. Verification: `python manage.py test api`, `python manage.py check`, `python manage.py makemigrations --check --dry-run`, frontend `npm test`, and `npm run build` passed. |
| 2026-05-12 | Codex | Fixed review blocker: soil presets now match the accepted FAO-56 plan exactly (`sand`, `light_loam`, `loam`, `clay_loam`), migration choices are aligned, and tests no longer assert obsolete `sandy_loam`/`clay` presets. |
| 2026-05-12 | Codex | Fixed review finding: all numeric FAO physical config values must be finite, latitude must be within `[-90, 90]`, and longitude within `[-180, 180]`. Added API regression tests for `Infinity`, `NaN`, and out-of-range coordinate rejection. |
