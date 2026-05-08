---
id: "008"
title: "Document MPC/AMPC demo workflow and validation gates"
status: "todo"
area: "docs"
agent: "@quality"
required_skills: ["docs", "quality"]
priority: "normal"
created_at: "2026-05-08"
due_date: null
started_at: null
completed_at: null
prd_refs: ["FR-017", "FR-021", "FR-033"]
blocks: []
blocked_by: ["004", "005", "006", "007"]
---

## Description

Cập nhật docs hướng dẫn chạy v2/v3, giải thích metric, safety gates, và demo flow. Tài liệu phải giúp người mới chạy simulation/recommendation/closed-loop dry checks mà không đọc code.

## Acceptance Criteria

- [ ] `MPC/docs/user/USER_GUIDE.md` có workflow chạy v2/v3.
- [ ] `MPC/docs/technical/CODEBASE_ONBOARDING.md` cập nhật module map sau implementation.
- [ ] Validation gates liệt kê rõ command và expected output.
- [ ] Review memory được cập nhật sau khi user chấp nhận.

## Completion Gates

- [ ] Logic: Demo workflow đúng thứ tự và không yêu cầu bước chưa implement.
- [ ] Nghiệp vụ: Tài liệu giải thích đúng v2 MPC, v3 AMPC, metric, và fail-safe.
- [ ] Security: Guide không chứa secret thật và cảnh báo rõ khi closed-loop.
- [ ] Test chạy thực tế: Docs được đối chiếu với code/CLI thực tế và validation commands đã chạy.

## Technical Notes

Không cập nhật `Kalman/docs/technical/CODEBASE_ONBOARDING.md` cho MPC implementation cho tới khi user review OK.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-08 | Codex | Task created |
