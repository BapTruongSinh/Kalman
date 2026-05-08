---
id: "004"
title: "Build v2 simulation CLI and baseline metrics report"
status: "completed"
area: "qa"
agent: "@quality"
required_skills: ["quality", "docs"]
priority: "high"
created_at: "2026-05-08"
due_date: null
started_at: "2026-05-09"
completed_at: "2026-05-09"
prd_refs: ["FR-017"]
blocks: ["005", "006"]
blocked_by: ["001", "002", "003"]
---

## Description

Tạo CLI `python -m mpc simulate` và `python -m mpc recommend`. Simulation phải so sánh MPC với threshold baseline, xuất JSON report có band violation, total pump seconds, switching count, và objective cost.

## Acceptance Criteria

- [x] CLI simulate đọc artifact và CSV input, ghi report JSON.
- [x] CLI recommend đọc state JSON và ghi recommendation JSON.
- [x] Baseline threshold controller được định nghĩa rõ trong report.
- [x] CLI smoke tests chạy không phụ thuộc Django.

## Completion Gates

- [x] Logic: CLI input/output path, baseline, và report metrics nhất quán, reproducible.
- [x] Nghiệp vụ: Simulation so sánh đúng band violation, pump seconds, switching count, objective cost.
- [x] Security: CLI không ghi secret/path nhạy cảm vào report và validate file path/config lỗi.
- [x] Test chạy thực tế: CLI smoke tests và report fixture test đã pass.

## Technical Notes

Fixture dùng synthetic ARX artifact và CSV nhỏ trong test để smoke CLI nhanh, không phụ thuộc Django/database.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-09 | Codex | Fixed post-review findings: `recommend` CLI now writes the public recommendation contract at top-level, simulation report objective cost resets soft daily cap per calendar day, and `CODEBASE_ONBOARDING.md` is synced after owner review. Verification: `python -m pytest MPC\tests -q` -> 31 passed; real CLI smoke for `recommend` and `simulate` OK. |
| 2026-05-09 | Codex | Implemented v2 CLI `simulate`/`recommend`, threshold baseline report, smoke tests, and docs. Verification: `python -m pytest MPC\tests -q` -> 30 passed; `python -m compileall -q MPC\mpc` OK. |
| 2026-05-08 | Codex | Task created |
