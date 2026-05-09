---
id: 000
title: Split Kalman algorithm package from Django server
status: completed
area: backend
required_skills:
  - planning
  - backend
  - quality
  - docs
created: 2026-05-09
---

# Task #000 - Split Kalman Algorithm Package From Django Server

## Goal

Make `Kalman/` a pure algorithm package with import name `kalman`, while the Django backend, dashboard, API, DB models, migrations, and business workflow live under `Server/`.

## Acceptance Criteria

- [x] `Kalman/kalman` exposes ingestion, prediction, Adaptive Kalman filter, metrics, and pure run config helpers.
- [x] `Kalman/kalman` has no imports from `django`, `rest_framework`, `estimation.models`, or Django settings.
- [x] `Server/backend` imports algorithm code from `kalman`.
- [x] Package checks pass:
  - `python -m pytest Kalman\tests -q`
  - `python -m compileall -q Kalman\kalman`
- [ ] Server checks pass after installing local editable packages:
  - `cd Server\backend; python manage.py check`
  - `cd Server\backend; python -m pytest estimation\tests -q`
