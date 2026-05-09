---
id: "006"
title: "Add experiment configuration persistence"
status: "completed"
area: "backend"
agent: "@backend-developer"
required_skill: "python-pro"
supporting_skills: ["database", "pydantic-models-py"]
priority: "normal"
created_at: "2026-04-13"
due_date: null
started_at: "2026-04-14"
completed_at: "2026-04-14"
prd_refs: ["FR-015", "FR-016", "FR-017", "FR-022", "NFR-009", "NFR-010"]
blocks: ["007", "008"]
blocked_by: ["001", "002"]
---

## Description

Add a configuration mechanism for sampling time, initial states, covariance-related parameters, ARX settings, and experiment metadata. Each run must preserve the configuration used to generate its results.

## Acceptance Criteria

- [x] Configuration values are not scattered as hard-coded constants.
- [x] Each experiment run records its configuration snapshot.
- [x] Configuration changes require authorization or are clearly restricted in the v1 prototype.
- [x] Replaying `../ARX/greenhouse_data.csv` with a saved config can regenerate comparable results.
- [x] Relevant documentation updated.

## Technical Notes

The exact auth approach is open; document any temporary v1 restriction.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-14 | Agent | Implemented `estimation.run_config`: `RunConfig` frozen dataclass, `ConfigFrozenError`, `create_run`, `load_config`, `update_config`; 74 tests (74 pass); `ARCHITECTURE.md` updated |
