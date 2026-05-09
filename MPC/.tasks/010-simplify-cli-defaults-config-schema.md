---
id: "010"
title: "Simplify MPC CLI defaults and export config schema"
status: "done"
area: "backend"
agent: "@builder"
required_skills: ["backend", "quality", "docs"]
priority: "normal"
created_at: "2026-05-09"
due_date: null
started_at: "2026-05-09"
completed_at: "2026-05-09"
prd_refs: []
blocks: []
blocked_by: []
---

## Description

Đơn giản hóa CLI MPC/AMPC để các tham số demo có default khi người dùng bỏ trống, thêm lệnh runtime `auto` cho closed-loop, và xuất schema/default config để website có thể load nhóm tham số người dùng cần nhập và nhóm tham số hệ thống giữ mặc định.

## Acceptance Criteria

- [x] `recommend`, `simulate`, `adaptive-simulate`, và closed-loop runtime có default path/output hợp lý khi chạy từ thư mục `MPC/`.
- [x] Có lệnh/API xuất config schema gồm default config, default runtime paths, nhóm `user_inputs`, và nhóm `system_defaults`.
- [x] Tests CLI/API cover default arguments và schema output.
- [x] Tài liệu CLI/API/config/user guide cập nhật đúng contract mới.

## Completion Gates

- [x] Logic: Flow CLI mới nhất quán, không phá contract output hiện có.
- [x] Nghiệp vụ: Bám đúng hướng AMPC auto runtime và website-loadable config.
- [x] Security: Actuator token vẫn lấy qua env, không hardcode secret; auto fail-closed khi thiếu actuator config.
- [x] Test chạy thực tế: Relevant command/check đã chạy và ghi lại.

## Technical Notes

- `simulate` và `adaptive-simulate` vẫn là workflow đánh giá; `auto` là alias runtime dễ nhớ cho `closed-loop`.
- Default paths là demo defaults, không thay thế live state source thật sau này.
- Website config schema là module/CLI JSON contract trong MPC, chưa phải HTTP endpoint.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-09 | human | Yêu cầu CLI dùng default khi bỏ trống tham số và xuất config schema cho website |
| 2026-05-09 | Codex | Task created |
| 2026-05-09 | Codex | Implemented CLI defaults, `auto`, `config-schema`, tests, docs, and smoke validation |
