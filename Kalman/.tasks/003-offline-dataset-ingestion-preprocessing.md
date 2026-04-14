---
id: "003"
title: "Implement offline dataset ingestion and preprocessing"
status: "todo"
area: "backend"
agent: "@backend-developer"
required_skill: "python-pro"
supporting_skills: ["data-engineer", "python-testing-patterns"]
priority: "high"
created_at: "2026-04-13"
due_date: null
started_at: null
completed_at: null
prd_refs: ["FR-001", "FR-003", "FR-004", "FR-005", "FR-006", "NFR-007"]
blocks: ["004", "005", "010", "011"]
blocked_by: ["001"]
---

## Description

Build the offline ingestion path for `../ARX/greenhouse_data.csv`. The loader should parse timestamped greenhouse records and apply validation/preprocessing for missing, malformed, out-of-range, or suspicious repeated values before data reaches ARX or Kalman.

## Acceptance Criteria

- [ ] CSV loader reads fields including `Timestamp`, `Soil_Moisture`, `Temperature`, `Humidity`, `Light`, `Drip`, `Mist`, and `Fan` where present.
- [ ] Validation flags missing, malformed, out-of-range, and suspicious repeated values.
- [ ] Preprocessing supports keep-last-valid, skip-measurement-update, or simple interpolation policy.
- [ ] Tests or reproducible checks run against `../ARX/greenhouse_data.csv`.
- [ ] Relevant documentation updated.

## Technical Notes

Keep preprocessing policy explicit in metadata so evaluation remains trustworthy.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
