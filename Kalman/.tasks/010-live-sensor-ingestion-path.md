---
id: "010"
title: "Add live sensor ingestion path"
status: "todo"
area: "backend"
agent: "@backend-developer"
required_skill: "python-pro"
supporting_skills: ["async-python-patterns", "backend-dev-guidelines"]
priority: "normal"
created_at: "2026-04-13"
due_date: null
started_at: null
completed_at: null
prd_refs: ["FR-002", "FR-003", "FR-004", "NFR-014", "NFR-015", "NFR-016"]
blocks: []
blocked_by: ["003"]
---

## Description

Add a live sensor ingestion path compatible with future ESP32-based nodes. It should share validation and preprocessing behavior with the offline CSV path so live and replayed data use the same pipeline semantics.

## Acceptance Criteria

- [ ] Live ingestion contract defines required timestamp and variable fields.
- [ ] Live samples use the same validation/preprocessing statuses as offline samples.
- [ ] Short device reconnect or sample gaps do not crash the pipeline.
- [ ] Operational endpoints are not exposed publicly without authentication.
- [ ] Relevant documentation updated.

## Technical Notes

Exact live protocol is open. Do not overbuild MQTT or device management until selected.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
