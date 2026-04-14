---
id: "006"
title: "Add experiment configuration persistence"
status: "todo"
area: "backend"
agent: "@backend-developer"
required_skill: "python-pro"
supporting_skills: ["database", "pydantic-models-py"]
priority: "normal"
created_at: "2026-04-13"
due_date: null
started_at: null
completed_at: null
prd_refs: ["FR-015", "FR-016", "FR-017", "FR-022", "NFR-009", "NFR-010"]
blocks: ["007", "008"]
blocked_by: ["001", "002"]
---

## Description

Add a configuration mechanism for sampling time, initial states, covariance-related parameters, ARX settings, and experiment metadata. Each run must preserve the configuration used to generate its results.

## Acceptance Criteria

- [ ] Configuration values are not scattered as hard-coded constants.
- [ ] Each experiment run records its configuration snapshot.
- [ ] Configuration changes require authorization or are clearly restricted in the v1 prototype.
- [ ] Replaying `../ARX/greenhouse_data.csv` with a saved config can regenerate comparable results.
- [ ] Relevant documentation updated.

## Technical Notes

The exact auth approach is open; document any temporary v1 restriction.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
