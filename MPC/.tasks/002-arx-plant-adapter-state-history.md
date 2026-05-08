---
id: "002"
title: "Implement ARX plant adapter and state history contracts"
status: "completed"
area: "backend"
agent: "@builder"
required_skills: ["backend", "quality"]
priority: "high"
created_at: "2026-05-08"
due_date: null
started_at: "2026-05-08"
completed_at: "2026-05-08"
prd_refs: ["FR-011", "FR-013", "FR-014"]
blocks: ["003", "004", "005", "006"]
blocked_by: ["001"]
---

## Description

Implement adapter đọc `../ARX/arx_model.json`, map `pump_seconds / 300` sang `Drip`, giữ disturbance forecast theo measured-hold, và chuẩn hóa state/history input cho solver. State phải ưu tiên `kf_x_posterior`, fallback raw soil moisture.

## Acceptance Criteria

- [x] Load artifact ARX và validate required inputs/coefficients.
- [x] Predict một bước và nhiều bước với control sequence `pump_seconds`.
- [x] Support measured-hold forecast cho `Temperature`, `Humidity`, `Light`.
- [x] Unit tests cover artifact load, pump mapping, missing state fallback, and invalid artifact.

## Completion Gates

- [x] Logic: Multi-step forecast dùng đúng history/order ARX và không mutate input ngoài ý muốn.
- [x] Nghiệp vụ: State ưu tiên Kalman posterior, fallback raw, và map `pump_seconds / 300` sang `Drip` đúng PRD.
- [x] Security: Artifact/state input được validate, lỗi artifact không làm crash silent.
- [x] Test chạy thực tế: `python -m pytest MPC/tests -q` passed 13 tests.

## Technical Notes

Không gọi code training trong `ARX/`; chỉ đọc artifact JSON.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-08 | Codex | Task created |
| 2026-05-08 | Codex | Started after reading rules, review memory, MPC onboarding/TODO/task, config, architecture, API, ADRs, and backend/quality skills. |
| 2026-05-08 | Codex | Completed core package, ARX artifact adapter, state/history contracts, measured-hold forecast, and tests; `python -m pytest MPC/tests -q` passed 10 tests. |
| 2026-05-08 | Codex | Superseded fix: initially changed ARX input lag `nb > 1` to `history[-lag]`, and kept valid `ControllerState.from_mapping()` checks for `last_pump_seconds`/`run_id`; later row below is authoritative for ARX lag alignment. |
| 2026-05-08 | Codex | Corrected ARX input lag alignment again after review: input lags are indexed from augmented `[*history, decision_record]`, so `lag 2` maps to `history[-1]`; regression test now expects `0.75`. |
