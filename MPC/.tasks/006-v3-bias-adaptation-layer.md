---
id: "006"
title: "Implement v3 AMPC bias adaptation layer"
status: "done"
area: "backend"
agent: "@builder"
required_skills: ["backend", "quality", "docs", "backend-security-coder"]
priority: "normal"
created_at: "2026-05-08"
due_date: null
started_at: "2026-05-09"
completed_at: "2026-05-09"
prd_refs: ["FR-020", "FR-021", "FR-022"]
blocks: ["007", "008"]
blocked_by: ["003", "004", "005"]
---

## Description

Thêm lớp AMPC bias correction dùng prediction error/Kalman residual gần đây để bù sai lệch mô hình trước khi solve MPC. Adaptive simulation phải so sánh v2 MPC và v3 AMPC.

## Acceptance Criteria

- [x] Bias estimator có guard cho missing/stale/outlier residual.
- [x] Adaptive solver dùng bias trong horizon prediction nhưng không phá pump bounds/safety.
- [x] Adaptive simulation report có v2 vs v3 metrics.
- [x] Tests chứng minh bias correction giảm error trên synthetic mismatch.

## Completion Gates

- [x] Logic: Bias correction ổn định, có guard outlier/stale/missing và không phá bounds.
- [x] Nghiệp vụ: AMPC v3 là bias adaptation stage, không tự ý thêm RLS/hybrid/hierarchical.
- [x] Security: Residual/state input lỗi không làm phát command unsafe.
- [x] Test chạy thực tế: Adaptive unit/simulation tests đã pass.

## Technical Notes

Chưa implement RLS model update ở task này; bias correction là AMPC stage đầu tiên.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-08 | Codex | Task created |
| 2026-05-09 | Codex | Implemented `AdaptiveConfig`, guarded `BiasEstimator`, `BiasCorrectedPlantModel`, adaptive simulation report with `mpc`/`ampc`/`threshold`, CLI `adaptive-simulate`, docs, and regression tests. |
| 2026-05-09 | Codex | Fixed review findings: direct `run_adaptive_simulation()` now force-enables bias adaptation for default config, added regression coverage, and synced `CODEBASE_ONBOARDING.md` after owner review. |
