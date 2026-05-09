---
id: "007"
title: "Store run outputs and pipeline logs"
status: "completed"
area: "backend"
agent: "@backend-developer"
required_skill: "database"
supporting_skills: ["python-pro", "observability-engineer"]
priority: "normal"
created_at: "2026-04-13"
due_date: null
started_at: "2026-04-14"
completed_at: "2026-04-14"
prd_refs: ["FR-013", "FR-014", "FR-015", "NFR-006", "NFR-007"]
blocks: ["008", "009", "012"]
blocked_by: ["002", "005", "006"]
---

## Description

Persist raw measurements, prediction outputs, filtered estimates, residuals/innovations, adaptive estimator status, timestamps, preprocessing statuses, pipeline statuses, and run metadata. This creates the traceability needed for debugging, reporting, AMPC handoff, and evaluation.

## Acceptance Criteria

- [x] Stored records distinguish raw input, prediction output, and filtered estimate values.
- [x] Each filtered value is traceable to raw input, prediction output, timestamp, residual/innovation, adaptive status, and configuration context.
- [x] Pipeline failures or skipped updates are logged with explicit status.
- [x] Relevant persistence checks pass.
- [x] Relevant documentation updated.

## Technical Notes

Follow the data model from task #002.

## Implementation

Created `estimation/pipeline/` package with two files:

### `pipeline/store.py`

| Function | Type | Description |
|----------|------|-------------|
| `map_result_to_cycle` | pure | Maps `CycleResult` + run metadata → unsaved `PipelineCycle` |
| `bulk_save_cycles` | DB | Batch-inserts via `bulk_create` (default batch_size=500) |
| `begin_run` | DB | PENDING → RUNNING with conditional `QuerySet.update` |
| `end_run` | DB | RUNNING → COMPLETED / FAILED / ABORTED |
| `RunStateError` | exception | Invalid lifecycle transition |

### `pipeline/__init__.py`

Re-exports the public API above.

### `tests/test_pipeline_store.py`

47 pytest cases across 4 test classes:
- `TestMapResultToCycle` (23 tests) — pure field mapping, kf_ prefix, raw sensor passthrough, error/skipped status
- `TestBulkSaveCycles` (6 tests) — count, queryability, uniqueness constraint, multi-batch
- `TestRunStatusTransitions` (11 tests) — status transitions, error guards, timestamp population
- `TestTraceability` (7 tests) — DB round-trip, FK chain, full field read-back, mixed status batch

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-14 | Codex | Implemented `estimation/pipeline/` — `store.py`, `__init__.py`; 47/47 tests pass; `manage.py check` clean; `ARCHITECTURE.md` updated with pipeline storage section |
