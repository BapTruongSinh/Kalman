---
id: "003"
title: "Implement v2 grid-shooting MPC recommendation solver"
status: "completed"
area: "backend"
agent: "@builder"
required_skills: ["backend", "quality", "backend-security-coder"]
priority: "high"
created_at: "2026-05-08"
due_date: null
started_at: "2026-05-08"
completed_at: "2026-05-08"
prd_refs: ["FR-010", "FR-012", "FR-015", "FR-016"]
blocks: ["004", "005", "006", "007"]
blocked_by: ["001", "002"]
---

## Description

Implement deterministic grid-shooting MPC cho một bơm nước. Solver tối ưu cost gồm band violation, tổng pump seconds, switching penalty, và soft daily cap; output chính là recommendation cho step đầu tiên.

## Acceptance Criteria

- [x] Solver luôn trả `pump_seconds` trong `[0, 300]`.
- [x] Output có đủ `pump_seconds`, `step_seconds`, `predicted_soil_moisture`, `target_band`, `cost`, `safety_status`, `reason`.
- [x] Cùng input cho cùng output.
- [x] Unit tests cover in-band, below-band, above-band, pump bound, switching penalty, and fail-safe status.

## Completion Gates

- [x] Logic: Solver deterministic, cost tính nhất quán, và command luôn trong bounds.
- [x] Nghiệp vụ: Recommendation output đúng contract PRD và không điều khiển phần cứng ở v2.
- [x] Security: Config/state bất hợp lệ fail closed, không tạo command nguy hiểm.
- [x] Test chạy thực tế: `python -m pytest MPC/tests -q` passed 26 tests.

## Technical Notes

V2 không điều khiển phần cứng. Nếu solver không tìm được candidate hợp lệ, trả pump off + reason rõ.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-08 | Codex | Task created |
| 2026-05-08 | Codex | Started after reading MPC rules, review memory, onboarding, TODO, task #003, config/API/architecture/PRD/ADRs, and required skills `backend`, `quality`, `backend-security-coder`. |
| 2026-05-08 | Codex | Completed deterministic grid-shooting beam solver, cost function, recommendation contract, fail-closed handling, and unit tests; `python -m pytest MPC/tests -q` passed 24 tests. |
| 2026-05-08 | Codex | Fixed review findings: forecast history now replaces latest record with `ControllerState`, future timestamps beyond clock skew fail closed, beam-grid approximation is documented, and preflight docs were synced. |
