---
id: "001"
title: "Resolve Adaptive Kalman and AMPC v1 decisions"
status: "todo"
area: "docs"
agent: "@planner"
required_skill: "software-architecture"
supporting_skills: ["statsmodels", "scientific-writing"]
priority: "high"
created_at: "2026-04-13"
due_date: null
started_at: null
completed_at: null
prd_refs: ["FR-001", "FR-007", "FR-010", "FR-020", "FR-022", "FR-023", "FR-024", "FR-025", "FR-026", "FR-027"]
blocks: ["002", "003", "004", "005", "006", "008", "009", "013"]
blocked_by: []
---

## Description

Resolve the open v1 technical decisions before implementation locks in the wrong shape. This includes the first Adaptive Kalman state variable set, CSV split policy, minimal adaptive rule, initial parameters, offline-vs-live priority, visualization scope, storage format, AMPC boundary, and final good-enough thresholds. ARX usage mode is now partially decided: v1 should use ARX as an explicit offline retrainable baseline rather than only a fixed saved artifact.

## Acceptance Criteria

- [ ] `PRD.md` open questions have accepted answers or explicit TBD owners.
- [ ] `docs/technical/DECISIONS.md` includes follow-up ADRs if any decision changes ADR-001 assumptions.
- [ ] Minimal Adaptive Kalman behavior is chosen or explicitly bounded as TBD with an owner.
- [ ] AMPC state/control/disturbance/cost/safety boundary is chosen enough for task #013 to proceed.
- [x] Prediction model path is clear: ARX is the explicit offline retrainable baseline in v1; LightGBM/XGBoost comparison is later unless explicitly pulled into v1.
- [ ] The first implementation target is clear enough for tasks #002-#005 to proceed without re-scoping.
- [ ] Relevant documentation updated.

## Technical Notes

Prefer an offline-first path using `../ARX/greenhouse_data.csv` unless the project owner chooses otherwise. Use a chronological split for train/validation/test so ARX retraining, parameter tuning, and final evaluation do not leak into each other. Use `docs/technical/ADAPTIVE_KALMAN_AMPC_NOTES.md` as the working synthesis from `BaoCao.md`, `Tonghop.md`, and `Tonghop2.md`; do not reduce the project back to standard Kalman + fixed MPC.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-14 | Codex | Re-scoped after user clarified project target as Adaptive Kalman + AMPC |
| 2026-04-14 | Project owner / Codex | Chose ARX as explicit offline retrainable v1 baseline |
