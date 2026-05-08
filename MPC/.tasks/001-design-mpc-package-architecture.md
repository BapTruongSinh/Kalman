---
id: "001"
title: "Design MPC package architecture and default config"
status: "completed"
area: "planning"
agent: "@planner"
required_skills: ["planning", "docs"]
priority: "high"
created_at: "2026-05-08"
due_date: null
started_at: "2026-05-08"
completed_at: "2026-05-08"
prd_refs: ["FR-010", "FR-012", "FR-015", "FR-016"]
blocks: ["002", "003", "004", "005", "006", "007"]
blocked_by: []
---

## Description

Chốt cấu trúc package Python, config mặc định, public dataclasses, CLI command layout, và default weights cho v2/v3. Task này biến PRD thành interface đủ cụ thể để implement không phải đoán.

## Acceptance Criteria

- [x] Có kiến trúc package và module map cho solver, plant model, simulation, adaptation, safety, actuator.
- [x] Có config schema cho step 300s, horizon 12, band 55-65%, pump bound 0-300s, switching penalty, soft daily cap.
- [x] Có quyết định grid resolution và default cost weights.
- [x] Cập nhật docs/ADR nếu quyết định ảnh hưởng kiến trúc.

## Completion Gates

- [x] Logic: Package/module boundaries không mâu thuẫn với `MPC/` độc lập và không kéo Django runtime vào v2.
- [x] Nghiệp vụ: Config/defaults bám PRD, Q&A onboarding, và ADR hiện có.
- [x] Security: Config design không hardcode actuator URL/token/secret và có chỗ validate unsafe values.
- [x] Test chạy thực tế: Chạy structural/docs checks phù hợp và ghi command trong History.

## Technical Notes

Không thêm SciPy/CVXPY ở v2. Giữ Django integration ngoài scope task này.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-08 | Codex | Task created |
| 2026-05-08 | Codex | Started task after reading project rules, review memory, MPC onboarding, TODO, PRD, ADRs, architecture, API, and Kalman AMPC handoff. |
| 2026-05-08 | Codex | Completed package/config design in `ARCHITECTURE.md`, `API.md`, `CONFIG.md`, and ADR-004. Structural checks passed: config/default grep, TODO-to-task mapping #000-#008, file existence checks, and trailing-whitespace scan. |
