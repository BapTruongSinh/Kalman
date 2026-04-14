---
id: "001"
title: "Resolve Adaptive Kalman and AMPC v1 decisions"
status: "completed"
area: "docs"
agent: "@planner"
required_skill: "software-architecture"
supporting_skills: ["statsmodels", "scientific-writing"]
priority: "high"
created_at: "2026-04-13"
due_date: null
started_at: "2026-04-14"
completed_at: "2026-04-14"
prd_refs: ["FR-001", "FR-007", "FR-010", "FR-020", "FR-022", "FR-023", "FR-024", "FR-025", "FR-026", "FR-027"]
blocks: ["002", "003", "004", "005", "006", "008", "009", "013"]
blocked_by: []
---

## Description

Resolve the open v1 technical decisions before implementation locks in the wrong shape. This includes the first Adaptive Kalman state variable set, CSV/MySQL split policy, minimal adaptive rule, initial parameters, offline-vs-live priority, visualization scope, storage format, AMPC boundary, and final good-enough thresholds. The result is now locked: v1 uses scalar `Soil_Moisture`, an explicit offline retrainable ARX baseline, bounded innovation-driven adaptive `R`, offline-first replay, MySQL as the local source of truth with CSV snapshots for import/export, and AMPC-ready docs/contracts without optimizer execution.

## Acceptance Criteria

- [x] `PRD.md` open questions have accepted answers or explicit TBD owners.
- [x] `docs/technical/DECISIONS.md` includes follow-up ADRs if any decision changes ADR-001 assumptions.
- [x] Minimal Adaptive Kalman behavior is chosen or explicitly bounded as TBD with an owner.
- [x] AMPC state/control/disturbance/cost/safety boundary is chosen enough for task #013 to proceed.
- [x] Prediction model path is clear: ARX is the explicit offline retrainable baseline in v1; LightGBM/XGBoost comparison is later unless explicitly pulled into v1.
- [x] The first implementation target is clear enough for tasks #002-#005 to proceed without re-scoping.
- [x] Relevant documentation updated.

## Technical Notes

Resolved path:

- Estimation target: scalar `Soil_Moisture`.
- Replay/data policy: load standardized time-series records from MySQL or a CSV snapshot, sort by timestamp, then apply `60/20/20` chronological split.
- Prediction path: ARX is the explicit offline retrainable baseline in v1.
- Adaptive rule: bounded innovation-driven adaptive `R`; `Q` stays fixed during a run and is chosen by validation tuning.
- Defaults: `x0 = first Soil_Moisture`, `P0 = 1.0`, `Q = 0.05` unless validation selects another value, `R0 = 1.0`, `R_min = 0.05`, `R_max = 25.0`, `alpha = 0.95`.
- Storage policy: MySQL from XAMPP is the local source of truth; CSV is snapshot/export and replay input.
- Visualization minimum: generated plots and dashboard views for raw, predicted, and filtered series.
- AMPC boundary: docs/contracts only in v1; no optimizer prototype, no closed-loop control.
- Good-enough gate: held-out replay completes without crash, logs row-level traceability, keeps innovation/`P`/`R` bounded, reaches `>= 20%` first-difference variance reduction with `>= 30%` as target, and keeps filtered RMSE/MAE within 5% of ARX prediction.

Use `docs/technical/ADAPTIVE_KALMAN_AMPC_NOTES.md` as the working synthesis from `BaoCao.md`, `Tonghop.md`, and `Tonghop2.md`; do not reduce the project back to standard Kalman + fixed MPC.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-14 | Codex | Re-scoped after user clarified project target as Adaptive Kalman + AMPC |
| 2026-04-14 | Project owner / Codex | Chose ARX as explicit offline retrainable v1 baseline |
| 2026-04-14 | Project owner / Codex | Locked v1 decisions across PRD, architecture, and ADRs; task marked complete |
