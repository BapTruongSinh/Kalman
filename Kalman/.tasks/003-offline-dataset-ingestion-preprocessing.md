---
id: "003"
title: "Implement offline dataset ingestion and preprocessing"
status: "completed"
area: "backend"
agent: "@backend-developer"
required_skill: "python-pro"
supporting_skills: ["data-engineer", "python-testing-patterns"]
priority: "high"
created_at: "2026-04-13"
due_date: null
started_at: "2026-04-14"
completed_at: "2026-04-14"
prd_refs: ["FR-001", "FR-003", "FR-004", "FR-005", "FR-006", "NFR-007"]
blocks: ["004", "005", "010", "011"]
blocked_by: ["001"]
---

## Description

Build the offline ingestion path for `../ARX/greenhouse_data.csv`. The loader should parse timestamped greenhouse records and apply validation/preprocessing for missing, malformed, out-of-range, or suspicious repeated values before data reaches ARX or Kalman.

## Acceptance Criteria

- [x] CSV loader reads fields including `Timestamp`, `Soil_Moisture`, `Temperature`, `Humidity`, `Light`, `Drip`, `Mist`, and `Fan` where present.
- [x] Validation flags missing, malformed, out-of-range, and suspicious repeated values.
  - *Malformed handling*: rows with unparseable timestamps are **rejected at loader level** (logged + skipped, never reach the validator). Numeric cells with non-parseable content are normalised to `None` by the loader's `_to_float` helper and reported as `status="missing"` by the validator. There is no separate `status="malformed"` value; the two-stage approach (loader rejects bad timestamps, validator flags numeric gaps) satisfies this criterion.
- [x] Preprocessing supports keep-last-valid (`kept_last`), skip-measurement-update (`skipped`), or simple interpolation (`interpolated`) policy. Policy constants `KEEP_LAST`, `INTERPOLATE`, `SKIP` are exported from the public API.
- [x] Tests or reproducible checks run against `../ARX/greenhouse_data.csv`.
- [x] Relevant documentation updated.

## Technical Notes

Keep preprocessing policy explicit in metadata so evaluation remains trustworthy.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-13 | Codex | Task created during `/start` onboarding |
| 2026-04-14 | Codex | Implemented `estimation/ingestion/` package: `loader.py` (RawRecord, load_csv, split_chronological), `validator.py` (ValidationResult, ValidationConfig, validate_record/batch), `preprocessor.py` (ProcessedRecord, keep_last/interpolate/skip), `__init__.py` public API. 30/30 pytest passed against real greenhouse_data.csv (105 120 rows). |
