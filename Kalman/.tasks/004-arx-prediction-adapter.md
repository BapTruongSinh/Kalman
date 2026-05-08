---
id: "004"
title: "Create replaceable prediction adapter contract with retrainable ARX baseline"
status: "done"
area: "backend"
agent: "@backend-developer"
required_skill: "python-pro"
supporting_skills: ["software-architecture", "statsmodels"]
priority: "high"
created_at: "2026-04-13"
due_date: null
started_at: "2026-04-14"
completed_at: "2026-04-14"
prd_refs: ["FR-007", "FR-008", "FR-009"]
blocks: ["005", "008", "009"]
blocked_by: ["001", "003"]
---

## Description

Wrap the existing ARX code behind a small prediction adapter that the estimator can call without depending on ARX internals. The adapter should support explicit offline retraining, loading the persisted ARX artifact for a run, and producing next-step predictions. It should define the inputs, outputs, error cases, and configuration fields needed for next-step prediction, while staying replaceable for later LightGBM/XGBoost comparison.

## Acceptance Criteria

- [x] Adapter contract defines input history/state and predicted output shape.
- [x] Adapter supports an explicit offline retrain step and records the artifact/config used by each run.
- [x] ARX output can be consumed by the Adaptive Kalman-ready estimator task without importing notebook-only code.
- [x] ARX errors or unavailable predictions return explicit status information.
- [x] Contract naming is model-agnostic enough that later LightGBM/XGBoost adapters can implement the same boundary.
- [x] Contract is documented in `docs/technical/ARCHITECTURE.md`.
- [x] Relevant tests or smoke checks pass.

## Technical Notes

Start from `../ARX/arx_pipeline.py` and `../ARX/arx_model.json` if those are the current reusable artifacts. Treat ARX as the retrainable offline baseline prediction model, not the only model the architecture will ever allow. Keep automatic online retraining and model registry out of v1.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-14 | Codex | Clarified adapter must stay replaceable for Adaptive Kalman + AMPC workflow |
| 2026-04-14 | Project owner / Codex | Chose retrainable offline ARX baseline for v1 |
| 2026-04-14 | Codex | Created `estimation/prediction/base.py` — `PredictionInput`, `PredictionResult`, `PredictionAdapter` ABC |
| 2026-04-14 | Codex | Created `estimation/prediction/arx_adapter.py` — `ARXTrainConfig` + `ARXPredictionAdapter` (OLS, artifact save/load, legacy format compat) |
| 2026-04-14 | Codex | Created `estimation/prediction/__init__.py` — public API exports |
| 2026-04-14 | Codex | Created `estimation/tests/test_prediction.py` — 50 tests (config, helpers, train, predict, artifact, API contract, real-data smoke) |
| 2026-04-14 | Codex | All 50 tests pass; `manage.py check` clean; no migration drift; `ARCHITECTURE.md` updated with adapter contract section |
