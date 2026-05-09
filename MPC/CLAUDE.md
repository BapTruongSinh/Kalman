# MPC - Claude Instructions

> Stack: Python package + CLI · ARX artifact reuse · optional HTTP actuator pilot
> Last updated: 2026-05-09

## Project Context

`MPC/` là project controller tách riêng khỏi `Kalman/`. Mục tiêu là xây dựng v2 MPC cho một bơm nước và v3 AMPC có bias adaptation, dùng state đã lọc từ Kalman và artifact `../ARX/arx_model.json` làm mô hình dự báo ban đầu.

**Tech stack summary**: No frontend in v2 · Python package/CLI · no DB ownership in v2 · optional HTTP actuator pilot in v3

---

## Critical Rules

1. `MPC/` là project root cho controller. Không viết code MPC vào `Green-House/backend` trừ khi có task integration rõ.
2. `ARX/` là context/artifact source. Không sửa training/data generator của `ARX/` nếu task chỉ là MPC.
3. `Kalman/` là upstream estimator/runtime. MPC được đọc output live/Kalman posterior, không phá live-only invariant hiện tại.
4. `MPC/PRD.md` là source of truth cho controller v2/v3. Chỉ sửa khi user yêu cầu hoặc khi đang chạy onboarding/task planning cho MPC.
5. `MPC/TODO.md` và `MPC/.tasks/` là backlog source of truth cho MPC. Làm xong task nào phải tick task đó và cập nhật file task tương ứng.
6. Trước mỗi task phải đọc `.claude/.claude/rules/`, `.claude/.claude/review/REVIEW.md`, `MPC/docs/technical/CODEBASE_ONBOARDING.md`, `MPC/TODO.md`, và task file liên quan.
7. Mỗi task phải có `required_skills` trong task file và phải dùng đúng skill local/system tương ứng trước khi thực hiện.
8. Mỗi task chỉ được hoàn tất khi qua đủ 4 gate: Logic, Nghiệp vụ, Security, Test chạy thực tế.
9. Không hardcode secret, actuator URL, Bearer token, hoặc thông số phần cứng nhạy cảm. Dùng config/env khi implement.
10. V2 không điều khiển phần cứng. V3 closed-loop phải fail closed: lỗi sensor/model/API/stale sample thì pump off + alert/log.
11. Chỉ cập nhật `MPC/docs/technical/CODEBASE_ONBOARDING.md` sau khi user review và xác nhận flow/code đã ổn.
12. Sau mỗi prompt/task, cập nhật `.claude/.claude/review/REVIEW.md`.
13. Tài liệu markdown trong `MPC/` dùng tiếng Việt có dấu, giữ nguyên thuật ngữ kỹ thuật cần thiết.

---

## Required Skills And Gates

| Area | Required skills |
|------|-----------------|
| planning | `planning`, `docs` |
| backend | `backend`, `quality`; thêm `backend-security-coder` nếu có actuator/auth/safety |
| qa | `quality` |
| docs | `docs`, `quality` |
| setup | `planning`, `docs` |

Mọi task phải có checklist `## Completion Gates` trong `.tasks/NNN-*.md`:

- Logic: luồng xử lý không mâu thuẫn và không tạo side effect sai.
- Nghiệp vụ: bám đúng PRD/Q&A/ADR của MPC.
- Security: không lộ secret, validate input/config, fail-safe đúng với actuator.
- Test chạy thực tế: có command/check cụ thể đã chạy hoặc ghi rõ vì sao chưa áp dụng.

---

## Environment & Commands

Current package status: task #008 documented the runnable v2/v3 demo workflow and validation gates after task #007 added importable `mpc` modules for config, state/history, ARX plant adapter, recommendation output, cost scoring, deterministic beam-grid shooting solver, simulation report, CLI `simulate`/`recommend`/`adaptive-simulate`/`closed-loop`, expanded validation tests, v3 AMPC bias adaptation, and v3 HTTP actuator pilot.

Current solver note: solver is deterministic beam-grid shooting with fail-closed validation. V2 CLI commands run without Django/database.

Hiện tại `MPC/` đã có core package Python cho config/state/plant adapter, recommendation output, cost scoring, deterministic beam-grid solver, simulation report, CLI `simulate`/`recommend`/`adaptive-simulate`/`closed-loop`, validation suite, bias adaptation v3, và HTTP actuator pilot có fail-safe.

- **Run tests**: `python -m pytest MPC/tests -q`
- **V2 simulate**: `cd MPC; python -m mpc simulate --max-steps 288`
- **V2 recommend**: `cd MPC; python -m mpc recommend`
- **V3 adaptive simulate**: `cd MPC; python -m mpc adaptive-simulate --max-steps 288`
- **V3 auto dry check**: `cd MPC; python -m mpc auto`
- **Config schema**: `cd MPC; python -m mpc config-schema`

---

## Key Documentation

@MPC/PRD.md
@MPC/TODO.md
@MPC/docs/technical/ONBOARDING_ANSWERS.md
@MPC/docs/technical/ARCHITECTURE.md
@MPC/docs/technical/DECISIONS.md
@MPC/docs/technical/CONFIG.md
@MPC/docs/technical/API.md
@MPC/docs/technical/DATABASE.md
@MPC/docs/technical/VALIDATION.md
@MPC/docs/technical/CODEBASE_ONBOARDING.md
@MPC/docs/plan/2026-05-08-mpc-v2-ampc-v3.md
@Green-House/docs/technical/CODEBASE_ONBOARDING.md
@Green-House/docs/technical/AMPC_MODELING_HANDOFF.md
