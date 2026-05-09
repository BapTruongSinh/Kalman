---
id: "008"
title: "Document MPC/AMPC demo workflow and validation gates"
status: "done"
area: "docs"
agent: "@quality"
required_skills: ["docs", "quality"]
priority: "normal"
created_at: "2026-05-08"
due_date: null
started_at: "2026-05-09"
completed_at: "2026-05-09"
prd_refs: ["FR-017", "FR-021", "FR-033"]
blocks: []
blocked_by: ["004", "005", "006", "007"]
---

## Description

Cập nhật docs hướng dẫn chạy v2/v3, giải thích metric, safety gates, và demo flow. Tài liệu phải giúp người mới chạy simulation/recommendation/closed-loop dry checks mà không đọc code.

## Acceptance Criteria

- [x] `MPC/docs/user/USER_GUIDE.md` có workflow chạy v2/v3.
- [x] `MPC/docs/technical/CODEBASE_ONBOARDING.md` cập nhật module map sau implementation.
- [x] Validation gates liệt kê rõ command và expected output.
- [x] Review memory được cập nhật sau task.

## Completion Gates

- [x] Logic: Demo workflow đúng thứ tự và không yêu cầu bước chưa implement.
- [x] Nghiệp vụ: Tài liệu giải thích đúng v2 MPC, v3 AMPC, metric, và fail-safe.
- [x] Security: Guide không chứa secret thật và cảnh báo rõ khi closed-loop.
- [x] Test chạy thực tế: Docs được đối chiếu với code/CLI thực tế và validation commands đã chạy.

## Technical Notes

Không cập nhật `Server/docs/technical/CODEBASE_ONBOARDING.md` cho MPC implementation cho tới khi có task integration hoặc yêu cầu rõ.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-08 | Codex | Task created |
| 2026-05-09 | Codex | Documented runnable v2/v3 demo workflow, added safe example state/config files, updated onboarding module map, expanded validation gates with expected outputs, and synced TODO/task status. |
