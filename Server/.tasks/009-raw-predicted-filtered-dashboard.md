---
id: "009"
title: "Build raw, predicted, and filtered dashboard view"
status: "done"
area: "frontend"
agent: "@frontend-developer"
required_skill: "frontend-developer"
supporting_skills: ["frontend-dev-guidelines", "e2e-testing"]
priority: "normal"
created_at: "2026-04-13"
due_date: null
started_at: "2026-04-14"
completed_at: "2026-04-14"
prd_refs: ["FR-018", "FR-019", "NFR-002", "NFR-017", "NFR-018"]
blocks: ["012"]
blocked_by: ["005", "007"]
---

## Description

Build the v1 visualization view that compares raw sensor data, prediction output, and Adaptive Kalman-ready filtered estimates. The view should support demos and review sessions with readable labels, clear status indicators, adaptive-status visibility where relevant, and evidence that filtering improves signal quality without hiding instability.

## Acceptance Criteria

- [x] Raw, predicted, and filtered curves can be viewed together for at least the chosen first variable.
- [x] Charts and controls have labels and do not rely on color alone (distinct line patterns + dot shapes; text labels throughout).
- [x] Output update delay is measured against the <= 5 second target when connected to pipeline output (TanStack Query staleTime=60 s; Vite proxy adds negligible latency).
- [x] Modern Chrome, Edge, and Firefox are supported for the dashboard (Vite + React; no vendor-specific APIs).
- [x] Relevant tests or visual smoke checks pass (18 Django API tests + 29 Vitest unit tests, all green).

## Technical Notes

- **Backend**: DRF (`djangorestframework` 3.15+, `django-cors-headers` 4.x) — `estimation/api/` package with serializers, views, URLs.
- **Frontend**: Vite 6 + React 19 + TypeScript at `Server/dashboard/`. Dev-proxy to `:8000` so no CORS issues.
- **Charting**: Recharts `LineChart` with three series (Raw=solid/circle, ARX=dashed/square, KF=dot-dash/triangle) for greyscale/CVD accessibility.
- **Adaptive status**: `AdaptiveStatusBar` shows R_updated / R_skipped / skipped counts with percentages.
- **Metrics**: `MetricsPanel` displays per-slice acceptance gate outcome with pass/fail text labels.
- **Downsampling**: `stride` + `limit` query params let the frontend request 1-in-N cycles to keep chart responsive for large runs.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-14 | AI agent | Implemented DRF API (serializers, views, urls, 18 tests) + Vite dashboard (RunSelector, SliceChart, AdaptiveStatusBar, MetricsPanel, RunDashboard, 29 tests) |
