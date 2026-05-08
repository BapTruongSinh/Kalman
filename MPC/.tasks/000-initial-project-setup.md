---
id: "000"
title: "Initial MPC project setup and onboarding documentation"
status: "completed"
area: "setup"
agent: "@planner"
required_skills: ["planning", "docs"]
priority: "high"
created_at: "2026-05-08"
due_date: null
started_at: "2026-05-08"
completed_at: "2026-05-08"
prd_refs: ["FR-001", "FR-002", "FR-003"]
blocks: ["001", "002", "003", "004", "005", "006", "007", "008"]
blocked_by: []
---

## Description

Khởi tạo `MPC/` như một project peer với `Kalman/`, dùng workflow onboarding từ `.claude/START_HERE.md` nhưng target là `MPC/`. Task này lưu Q&A đã chốt, tạo PRD/README/CLAUDE/TODO/docs/task backlog để các bước implementation v2/v3 có source of truth rõ.

## Acceptance Criteria

- [x] `MPC/` có `README.md`, `PRD.md`, `CLAUDE.md`, `TODO.md`, `.tasks/`, và docs cần thiết.
- [x] Q&A onboarding MPC được lưu trong `MPC/docs/technical/ONBOARDING_ANSWERS.md`.
- [x] `MPC/TODO.md` chỉ chứa task thật, không giữ placeholder.
- [x] Task #000 được đánh dấu completed.

## Completion Gates

- [x] Logic: Cấu trúc `MPC/` tách khỏi `Kalman/`, không tạo runtime side effect.
- [x] Nghiệp vụ: Q&A và backlog bám đúng quyết định v2 MPC, v3 AMPC, một bơm nước.
- [x] Security: Không ghi secret, actuator URL, hoặc token vào scaffold.
- [x] Test chạy thực tế: Required-file check, TODO/task mapping, placeholder grep, và `git diff --check` đã chạy.

## Technical Notes

Không implement solver/controller trong task này. Implementation bắt đầu từ task #001.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-08 | Project owner / Codex | Task created and completed from MPC onboarding request |
