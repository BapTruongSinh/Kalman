---
id: "008"
title: "Build evaluation metrics and report export"
status: "done"
area: "qa"
agent: "@qa-engineer"
required_skill: "python-pro"
supporting_skills: ["statsmodels", "matplotlib", "seaborn"]
priority: "normal"
created_at: "2026-04-13"
due_date: null
started_at: "2026-04-14"
completed_at: "2026-04-15"
prd_refs: ["FR-020", "FR-021", "FR-022", "NFR-001", "NFR-002", "NFR-003", "NFR-004"]
blocks: ["012"]
blocked_by: ["005", "007"]
---

## Description

Add evaluation outputs that prove whether the Adaptive Kalman-ready estimator and prediction baseline are working well. Metrics should include variance reduction, residual/innovation stability, MAE or RMSE where reference data is available, cycle success rate, latency, sample loss, adaptive-status traceability, and reproducibility from saved configuration. If AMPC simulation is included later, extend the report with water use, energy, stress time, and actuator switching metrics.

## Acceptance Criteria

- [x] Evaluation reports include variance reduction and residual behavior.
- [x] MAE or RMSE is calculated when reference data is available.
- [x] Cycle success rate, latency, update delay, and sample loss can be measured.
- [x] Adaptive estimator status or rationale is included when adaptive behavior affects a cycle.
- [x] AMPC-readiness metrics or placeholders are documented if controller simulation is not part of v1.
- [x] Report-ready export is generated for presentation or final report use.
- [x] Relevant tests or reproducibility checks pass.

## Technical Notes

Use `../ARX/greenhouse_data.csv` as the default reproducible evaluation input unless task #001 chooses a different baseline.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-14 | Agent | Implementation started |
| 2026-04-15 | Agent | Completed — `estimation/evaluation/` package added; `SliceMetrics`, `compute_metrics`, `evaluate_slice/all_slices`, `build_text_report`, `export_to_csv`, `export_plots` (optional matplotlib); 53 new tests; migration 0003 for `latency_ms` on `PipelineCycle` and adaptive/latency fields on `EvaluationSummary`; ARCHITECTURE.md updated |
