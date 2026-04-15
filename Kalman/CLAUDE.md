# Adaptive Kalman + AMPC - Claude Instructions

> Stack: Vite + Python/Django + MySQL from XAMPP + Django ORM + AWS target
> Last updated: 2026-04-14

## Project Context

Project target directory is `Kalman/`. The sibling `../ARX/` folder is read-only context for ARX prediction assets and datasets unless the user explicitly asks to modify it. The `.claude/` folder is for agent/template management.

The project direction is Adaptive Kalman estimation plus AMPC for a smart greenhouse. v1 still focuses on a reliable staged pipeline `Sensor/Dataset -> Preprocess -> Prediction Adapter -> Adaptive Kalman-ready Update -> Store -> Visualize -> Evaluate`, while keeping AMPC state/control/disturbance contracts visible.

The current repository includes `../ARX/greenhouse_data.csv` and existing ARX code. ARX is the first prediction baseline, not a permanent architecture lock-in. Full autonomous AMPC actuation is reserved until the PRD/task decisions promote it, but Adaptive Kalman behavior and AMPC-ready interfaces must not be treated as out-of-scope background noise.

**Tech stack summary**: Vite frontend + Python/Django backend + MySQL from XAMPP + Django ORM + AWS deployment target.

---

## Critical Rules

1. `PRD.md` is the product source of truth. Only edit it when the human explicitly asks for requirement changes.
2. `TODO.md` and matching `.tasks/NNN-*.md` files are the backlog source of truth.
3. Keep prediction, estimator, and AMPC modules loosely coupled. ARX is the first prediction baseline; the estimator must stay Adaptive Kalman-ready.
4. Do not implement full closed-loop autonomous AMPC scheduling, model registry, or multi-greenhouse support in v1 unless the PRD changes. Do keep estimator code and docs Adaptive Kalman-ready, and keep state/control/disturbance boundaries compatible with AMPC.
5. Do not hardcode secrets, credentials, database URLs, AWS values, or environment-specific settings.
6. Update relevant docs after significant implementation changes.
7. Run the relevant checks before marking an implementation task complete.
8. Báo cáo, tóm tắt, cập nhật tiến độ và câu trả lời cho người dùng mặc định dùng tiếng Việt có dấu.

---

## Project Structure

```text
../ARX/
  greenhouse_data.csv
  arx_pipeline.py
./
docs/
  technical/
  content/
  user/
.tasks/
CLAUDE.md
PRD.md
README.md
TODO.md
```

---

## Code Style

- **Frontend formatter**: Prettier
- **Frontend linter**: ESLint
- **Frontend tests**: Vitest
- **Backend language**: Python
- **Backend framework**: Django, assumed from Django ORM selection
- **Database access**: Django ORM against MySQL from XAMPP
- **Import style**: Follow each stack's standard module organization until a project convention is formalized.
- **Comments**: Use comments only to explain non-obvious modeling, filtering, or data-quality decisions.

---

## Testing Conventions

- **Unit tests**: Vitest for frontend.
- **Backend tests**: TBD. Use a Python test runner once the Django backend scaffold exists.
- **Data checks**: v1 tasks that touch estimation should verify behavior against `../ARX/greenhouse_data.csv`.
- **Expected evaluation evidence**: cycle success rate, latency, variance reduction, residual/innovation stability, adaptive status traceability, AMPC readiness, sample loss, and reproducibility from saved configuration.

---

## Environment & Commands

- **Node**: latest, not pinned yet.
- **Package manager**: npm.
- `npm run dev` - start the frontend development server.
- `npm run build` - build the frontend.
- `npm test` - run unit tests.
- `npm start` - start the application entrypoint once configured.
- Backend/Django commands are TBD.

---

## Key Documentation

- `PRD.md`
- `TODO.md`
- `docs/technical/ARCHITECTURE.md`
- `docs/technical/DESIGN_SYSTEM.md`
- `docs/technical/DECISIONS.md`
- `docs/technical/ONBOARDING_ANSWERS.md`
- `docs/technical/ADAPTIVE_KALMAN_AMPC_NOTES.md`
- `docs/technical/API.md`
- `docs/technical/DATABASE.md`
- `docs/technical/METHODOLOGY_V1.md`
- `docs/user/USER_GUIDE.md`
- `docs/content/CONTENT_STRATEGY.md`
