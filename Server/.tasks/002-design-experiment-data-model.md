---
id: "002"
title: "Design experiment data model and storage plan"
status: "completed"
area: "database"
agent: "@database-expert"
required_skill: "database-design"
supporting_skills: ["software-architecture", "python-pro"]
priority: "high"
created_at: "2026-04-13"
due_date: null
started_at: "2026-04-14"
completed_at: "2026-04-14"
prd_refs: ["FR-013", "FR-014", "FR-015", "FR-016", "NFR-006", "NFR-007"]
blocks: ["006", "007", "008", "009"]
blocked_by: ["001"]
---

## Description

Design the MySQL/Django ORM model for experiment runs, raw measurements, prediction outputs, filtered estimates, residuals/innovations, adaptive estimator status, preprocessing status, and configuration snapshots. The model must support traceability from each filtered value back to its source data, prediction baseline, adaptive behavior, and settings.

## Acceptance Criteria

- [x] Proposed schema covers raw measurements, prediction outputs, filtered estimates, residuals/innovations, adaptive status, timestamps, statuses, and run configs.
- [x] Relationships and indexes are documented in `docs/technical/DATABASE.md`.
- [x] Storage format decision is documented: MySQL only, CSV export, or both.
- [x] Relevant documentation updated.

## Technical Notes

Use MySQL from XAMPP and Django ORM per onboarding answers.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-14 | Codex | Designed full 5-table schema (experiment_runs, experiment_configs, arx_artifacts, pipeline_cycles, evaluation_summaries); wrote DATABASE.md with all columns, indexes, query patterns, and storage decision; created Django ORM models, backend scaffold, settings, requirements, and .env.example |
