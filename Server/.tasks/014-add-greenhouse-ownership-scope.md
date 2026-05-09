---
id: "014"
title: "Add greenhouse ownership scope for live data"
status: "completed"
area: "database"
agent: "@database-engineer"
required_skill: "database"
supporting_skills: ["backend", "quality"]
priority: "high"
created_at: "2026-05-09"
due_date: null
started_at: "2026-05-09"
completed_at: "2026-05-09"
prd_refs: ["FR-025", "FR-026", "FR-027"]
blocks: []
blocked_by: ["010", "013"]
---

## Description

Add explicit greenhouse scoping for live sensor data and prediction outputs. The product is multi-user: one user can own multiple greenhouses, and all estimation/control records must resolve to the correct greenhouse. Prediction tables should store `greenhouse_id`; they should not duplicate `user_id` because greenhouse ownership already provides the user relationship.

## Acceptance Criteria

- [x] A `Greenhouse` table exists and references the Django user table.
- [x] `ExperimentRun` and persisted prediction cycles are scoped by `greenhouse_id`, not a duplicated run/user owner field.
- [x] Live ingest authorizes against `greenhouse.owner_id` before accepting samples.
- [x] Dashboard/API queries can return runs for the authenticated user's greenhouses and optionally filter by greenhouse.
- [x] Existing live data is backfilled into a default greenhouse during migration.
- [x] Relevant tests written and passing.
- [x] Relevant documentation updated.

## Completion Gates

- [x] Logic: `Greenhouse` is the single ownership source; `ExperimentRun` and `PipelineCycle` persist `greenhouse_id`, while user ownership is derived through `Greenhouse.owner`.
- [x] Nghiệp vụ: The schema supports one user owning multiple greenhouses, live data resolves to the correct greenhouse, and prediction records do not duplicate `user_id`.
- [x] Security: Live ingest requires DRF token auth, authorizes against `run.greenhouse.owner_id`, rejects inactive greenhouses, and dashboard run queries are scoped to the authenticated user's greenhouses before optional `greenhouse_id` filtering.
- [x] Test chạy thực tế: `python manage.py check` OK; `python manage.py makemigrations --check --dry-run` no changes; `python manage.py migrate --check` OK; `showmigrations estimation` shows `0009_greenhouse_scope` applied; DB verification shows `greenhouses=1`, `runs_missing_greenhouse=0`, `cycles_missing_greenhouse=0`, `cycles_total=105120`; `python -m pytest estimation/tests -q` -> 81 passed; targeted API/ingest/run_config/store tests -> 65 passed; `python -m compileall -q estimation` OK; `git diff --check` only LF/CRLF warnings.

## Technical Notes

Treat this as the database foundation before wiring AMPC online execution. The ARX artifact path and sensor-state source cleanup will be handled after this schema change; this task only makes the persisted data model correct for per-greenhouse state lookup.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-05-09 | human | Clarified that greenhouse owns user, so prediction records only need `greenhouse_id` |
| 2026-05-09 | Codex | Task created and started |
| 2026-05-09 | Codex | Completed: added greenhouse model/migration, switched run/cycle persistence and ingest auth to greenhouse scope, updated dashboard filtering, docs, and tests |
| 2026-05-09 | Codex | Added explicit 4-gate completion evidence after owner review found the task file lacked gate proof |
