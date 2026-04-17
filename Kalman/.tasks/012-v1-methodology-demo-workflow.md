---
id: "012"
title: "Document v1 methodology and demo workflow"
status: "completed"
area: "docs"
agent: "@documentation-writer"
required_skill: "documentation"
supporting_skills: ["scientific-writing", "software-architecture"]
priority: "normal"
created_at: "2026-04-13"
due_date: null
started_at: "2026-04-15"
completed_at: "2026-04-15"
prd_refs: ["FR-018", "FR-020", "FR-021", "FR-022"]
blocks: []
blocked_by: ["005", "008", "009", "011"]
---

## Description

Document the final v1 method and demo path so the project can be defended academically. The writeup should explain where data comes from, how the prediction adapter works with ARX as baseline, how the Adaptive Kalman-ready estimator updates, what metrics prove improvement, how the workflow connects to AMPC, and what is postponed to a later implementation step.

## Acceptance Criteria

- [x] `docs/user/USER_GUIDE.md` explains how to run the v1 demo or replay workflow.
- [x] Technical docs explain prediction output, Adaptive Kalman update, residuals/innovations, adaptive status, and evaluation outputs.
- [x] Technical docs explain AMPC-ready state/control/disturbance/cost/safety contracts, even if full closed-loop actuation is postponed.
- [x] Out-of-scope later items are clearly listed without incorrectly excluding Adaptive Kalman or AMPC from the project topic.
- [x] The documented workflow can reproduce results from repo-root `ARX/greenhouse_data.csv`.

## Technical Notes

Use exported metrics and dashboard screenshots or plots once available.

**Delivered**: `docs/technical/METHODOLOGY_V1.md` (methodology + AMPC boundary + evaluation); expanded `docs/user/USER_GUIDE.md` (dashboard, API, Django shell CSV→DB recipe, pytest reproduction); links from `ARCHITECTURE.md`, `API.md`, `CLAUDE.md`.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-15 | Cursor | Task #012 completed — methodology + user runbook |
