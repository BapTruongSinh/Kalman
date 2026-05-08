---
id: "005"
title: "Add v2 unit, CLI smoke, and simulation regression tests"
status: "completed"
area: "qa"
agent: "@quality"
required_skills: ["quality", "docs"]
priority: "normal"
created_at: "2026-05-08"
due_date: null
started_at: "2026-05-09"
completed_at: "2026-05-09"
prd_refs: ["FR-010", "FR-011", "FR-012", "FR-013", "FR-014", "FR-015", "FR-016", "FR-017"]
blocks: ["006", "007", "008"]
blocked_by: ["002", "003", "004"]
---

## Description

Hoàn thiện test suite cho v2 để đảm bảo controller có thể phát triển tiếp lên AMPC mà không bị regression. Test cover config validation, solver determinism, ARX mapping, CLI smoke, và simulation metric.

## Acceptance Criteria

- [x] `python -m pytest MPC/tests -q` pass.
- [x] Có tests cho happy path và edge cases.
- [x] Có regression test so sánh MPC/baseline trên fixture ổn định.
- [x] Có tài liệu validation gates.

## Completion Gates

- [x] Logic: Test suite cover đúng các branch solver/config/ARX/CLI chính, không test implementation detail giòn.
- [x] Nghiệp vụ: Tests trace được tới FR v2 và metric demo cần bảo vệ.
- [x] Security: Có test cho input lỗi/config lỗi/fail-safe cơ bản.
- [x] Test chạy thực tế: `python -m pytest MPC/tests -q` pass và kết quả được ghi vào History.

## Technical Notes

Không dùng production data thật ngoài synthetic/demo artifact đã có trong repo. Regression fixture dùng synthetic ARX artifact/CSV ổn định để bảo vệ public metrics và CLI contracts.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-09 | Codex | Fixed post-review findings: config JSON integer fields are now strict and reject floats/strings/bools; `required_skills` includes `docs`; README/CLAUDE status synced after task #005. Verification: `python -m pytest MPC\tests -q` -> 48 passed; `python -m compileall -q MPC\mpc` OK. |
| 2026-05-09 | Codex | Completed task #005: added config validation tests, CLI error smoke tests, simulation regression tests, and `docs/technical/VALIDATION.md`. Verification: `python -m pytest MPC\tests -q` -> 43 passed; `python -m compileall -q MPC\mpc` OK. |
| 2026-05-08 | Codex | Task created |
