# Server - Claude Instructions

> Stack: Django + DRF + MySQL + Vite dashboard + local `kalman` and `mpc` packages
> Last updated: 2026-05-09

## Project Context

`Server/` owns the Django backend, dashboard, database/API/auth/business workflow, live sensor ingestion, AMPC recommendation persistence, and optional actuator integration.

Sibling packages:

- `../Kalman/`: pure Adaptive Kalman algorithm package, import name `kalman`.
- `../MPC/`: pure MPC/AMPC controller package, import name `mpc`.
- `../ARX/`: research/training folder and default ARX artifact source, especially `ARX/arx_model.json`.

Production scope includes multi-user and multi-greenhouse support. A user can own multiple greenhouses, and every state/recommendation/control request must be scoped through greenhouse ownership.

## Critical Rules

1. `PRD.md` is the product source of truth. Only edit it when the human explicitly asks for requirement changes.
2. `TODO.md` and matching `.tasks/NNN-*.md` files are the backlog source of truth.
3. Keep algorithm code out of `Server/` unless it is integration glue. Adaptive Kalman logic belongs in `Kalman/kalman`; MPC/AMPC logic belongs in `MPC/mpc`.
4. Multi-user and multi-greenhouse are mandatory Server requirements. Verify greenhouse ownership before reading state, running AMPC, returning dashboard JSON, or sending actuator commands.
5. Do not hardcode secrets, credentials, database URLs, actuator URLs/tokens, AWS values, or environment-specific settings.
6. Update relevant docs after significant implementation changes.
7. Run the relevant checks before marking an implementation task complete.
8. Default user-facing progress reports and summaries should be Vietnamese.
9. Before each new task, read this file, `.claude/.claude/rules/`, `.claude/.claude/review/REVIEW.md`, `docs/technical/CODEBASE_ONBOARDING.md`, `TODO.md`, and the task file.
10. Do not update `docs/technical/CODEBASE_ONBOARDING.md` immediately after code changes. Update it only after the user has reviewed and accepted the flow/code.

## Project Structure

```text
Server/
  backend/       # Django backend, DRF API, ORM, migrations
  dashboard/     # Vite + React dashboard
  docs/          # Server docs
  .tasks/        # Server task history
  CLAUDE.md
  PRD.md
  README.md
  TODO.md
```

## Commands

- Backend dev: `cd Server/backend; python manage.py runserver`
- Backend checks: `cd Server/backend; python manage.py check`
- Backend tests: `cd Server/backend; python -m pytest estimation/tests -q`
- Dashboard dev: `cd Server/dashboard; npm run dev`
- Dashboard tests: `cd Server/dashboard; npm test -- --run`
- Dashboard build: `cd Server/dashboard; npm run build`
- Kalman package tests: `python -m pytest Kalman/tests -q`
- MPC package tests: `python -m pytest MPC/tests -q`

## Key Documentation

- `PRD.md`
- `TODO.md`
- `docs/technical/ARCHITECTURE.md`
- `docs/technical/DESIGN_SYSTEM.md`
- `docs/technical/DECISIONS.md`
- `docs/technical/ONBOARDING_ANSWERS.md`
- `docs/technical/CODEBASE_ONBOARDING.md`
- `docs/technical/API.md`
- `docs/technical/DATABASE.md`
- `docs/user/USER_GUIDE.md`
