---
id: "005"
title: "Add v2 unit, CLI smoke, and simulation regression tests"
status: "todo"
area: "qa"
agent: "@quality"
required_skills: ["quality"]
priority: "normal"
created_at: "2026-05-08"
due_date: null
started_at: null
completed_at: null
prd_refs: ["FR-010", "FR-011", "FR-012", "FR-013", "FR-014", "FR-015", "FR-016", "FR-017"]
blocks: ["006", "007", "008"]
blocked_by: ["002", "003", "004"]
---

## Description

Hoàn thiện test suite cho v2 để đảm bảo controller có thể phát triển tiếp lên AMPC mà không bị regression. Test phải cover config validation, solver determinism, ARX mapping, CLI smoke, và simulation metric.

## Acceptance Criteria

- [ ] `python -m pytest MPC/tests -q` pass.
- [ ] Có tests cho happy path và edge cases.
- [ ] Có regression test so sánh MPC/baseline trên fixture ổn định.
- [ ] Có tài liệu validation gates.

## Completion Gates

- [ ] Logic: Test suite cover đúng các branch solver/config/ARX/CLI chính, không test implementation detail giòn.
- [ ] Nghiệp vụ: Tests trace được tới FR v2 và metric demo cần bảo vệ.
- [ ] Security: Có test cho input lỗi/config lỗi/fail-safe cơ bản.
- [ ] Test chạy thực tế: `python -m pytest MPC/tests -q` pass và kết quả được ghi vào History.

## Technical Notes

Không dùng production data thật ngoài synthetic/demo artifact đã có trong repo.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-08 | Codex | Task created |
