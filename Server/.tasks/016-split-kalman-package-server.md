---
id: "016"
title: "Split Kalman algorithm package from Django server"
status: "completed"
area: "backend"
agent: "@backend-developer"
required_skill: "backend"
supporting_skills:
  - "planning"
  - "quality"
  - "docs"
priority: "high"
created_at: "2026-05-09"
due_date: null
started_at: "2026-05-09"
completed_at: "2026-05-09"
prd_refs: []
blocks: []
blocked_by: ["015"]
---

## Description

Tach `Kalman/` thanh package thuat toan doc lap va tao `Server/` rieng cho Django backend, dashboard, database, API, auth, va workflow business. Sau refactor, `Server/` goi package `kalman` va `mpc`; `Kalman/` khong con chua Django app, DB models, migrations, API, hay frontend.

## Acceptance Criteria

- [x] `Server/backend` chua Django backend hien tai, app label `estimation` va migration history giu nguyen.
- [x] `Server/dashboard` chua React/Vite dashboard hien tai.
- [x] `Kalman/kalman` la package Python import duoc bang `kalman`.
- [x] Pure algorithm duoc tach vao package: ingestion, prediction adapter, Adaptive Kalman filter, metrics, run config dataclass.
- [x] `Kalman/kalman` khong import `django`, `rest_framework`, `estimation.models`, hoac `config.settings`.
- [x] `Server/backend/requirements.txt` cai editable ca `../../Kalman` va `../../MPC`.
- [x] Endpoint va DB schema khong doi.
- [x] Relevant tests/checks pass.
- [x] Relevant docs/TODO/task history updated, tru `CODEBASE_ONBOARDING.md` cho toi khi owner review OK.

## Completion Gates

### Logic

- [x] Server va algorithm package co boundary ro: pure code o `Kalman/`, integration/persistence/API o `Server/`.
- [x] Import path moi khong tao circular dependency giua `Server` va `Kalman`.
- [x] DB migration/table name khong doi.

### Nghiep vu

- [x] Production flow van la sensor -> Server -> DB -> Kalman filter -> MPC/AMPC -> dashboard.
- [x] Multi-user/multi-greenhouse workflow van nam o Server.

### Security

- [x] Auth/authz behavior cua Server khong doi.
- [x] Khong expose secret/model path/token moi qua refactor.

### Test chay thuc te

- [x] Kalman package tests pass.
- [x] Server backend checks/tests pass.
- [x] Server dashboard tests/build pass.
- [x] MPC tests pass.

## Technical Notes

Plan file: `Server/docs/plan/2026-05-09-split-kalman-server.md` from repo root.

Use `kalman` as package import name per owner decision. Keep Django app label `estimation` to avoid DB migration/table churn.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-05-09 | human | Requested repo split: `Kalman/` must be algorithm package only; create separate `Server/` for Django/backend/dashboard |
| 2026-05-09 | Codex | Created task and started implementation |
| 2026-05-09 | Codex | Moved Django/dashboard/docs/task history to `Server/`, created pure `Kalman/kalman` package, updated imports/requirements/docs, and ran validation. Remaining gate is MySQL-backed backend validation because local MySQL refused connection. |
| 2026-05-09 | Codex | Re-ran MySQL-backed gates after MySQL was started: `migrate --check` passed and full backend tests passed (`96 passed`). Marked task complete. |
| 2026-05-09 | Codex | Fixed post-review deploy/doc findings: split Server dependency files into deploy package requirements and monorepo editable requirements, added Server artifact default/docs, clarified Kalman is algorithm-support not strict filter-only, and updated stale MPC README integration wording. |
