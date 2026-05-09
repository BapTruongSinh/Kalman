---
id: "009"
title: "Normalize MPC objective cost by pump bounds and daily cap"
status: "done"
area: "backend"
agent: "@builder"
required_skills: ["planning", "backend", "quality", "docs"]
priority: "normal"
created_at: "2026-05-09"
due_date: null
started_at: "2026-05-09"
completed_at: "2026-05-09"
prd_refs: ["FR-015", "FR-017"]
blocks: []
blocked_by: ["003", "005"]
---

## Description

Sửa objective cost theo công thức đã chốt: water/switching normalize bằng `pump.max_seconds`, soft daily cap tính theo tổng planned excess trên `soft_daily_pump_cap_seconds`, band/terminal vẫn dùng band error bình phương.

## Acceptance Criteria

- [x] `score_trajectory()` dùng `u_i / u_max` cho water penalty.
- [x] `score_trajectory()` dùng `(u_i - u_{i-1}) / u_max` cho switching penalty.
- [x] Daily cap penalty dùng tổng planned excess chia cho daily cap, không chia cho `step_seconds`.
- [x] Simulation report cost breakdown dùng cùng normalization và daily cap reset theo ngày lịch.
- [x] Regression tests và docs công thức được cập nhật.

## Completion Gates

- [x] Logic: Công thức cost đúng với công thức owner chốt và không lệch solver/report.
- [x] Nghiệp vụ: Band tracking vẫn dùng độ lệch khỏi band, terminal penalty vẫn giữ trạng thái cuối horizon an toàn.
- [x] Security: Không chạm actuator secret/config nhạy cảm.
- [x] Test chạy thực tế: MPC tests, compileall, và CLI smoke pass.

## Technical Notes

`PumpLimits.to_duty()` vẫn giữ `pump_seconds / step_seconds` vì đó là mapping sang ARX input `Drip`. Chỉ objective cost đổi normalization sang `pump.max_seconds`.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-09 | Codex | Task created from owner-approved objective cost formula. |
| 2026-05-09 | Codex | Implemented cost normalization, updated report scoring, tests, docs, TODO/task status, and validation gates. |
