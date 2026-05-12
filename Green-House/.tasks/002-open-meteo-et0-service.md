---
id: "002"
title: "Add Open-Meteo hourly ET0 service with cache and fail-closed behavior"
status: "completed"
area: "backend"
agent: "@builder"
required_skills: ["backend", "quality", "backend-security-coder", "docs"]
priority: "high"
created_at: "2026-05-12"
due_date: null
started_at: "2026-05-12"
completed_at: "2026-05-12"
prd_refs: []
blocks: ["003", "006"]
blocked_by: []
---

## Description

Add a backend ET0 service for AMPC that fetches hourly FAO ET0 from Open-Meteo using greenhouse coordinates, caches it, and fails closed when no valid ET0 is available.

The first implementation should use Open-Meteo's hourly `et0_fao_evapotranspiration` instead of locally calculating full Penman-Monteith.

## Acceptance Criteria

- [x] Add service module for ET0 fetching/cache, for example `Green-House/backend/api/et0.py`.
- [x] Query Open-Meteo with:
  - greenhouse latitude
  - greenhouse longitude
  - hourly `et0_fao_evapotranspiration`
  - timezone handling suitable for hourly lookup
- [x] Cache ET0 hourly by greenhouse/time bucket.
- [x] On Open-Meteo failure:
  - use recent valid cache when still fresh
  - otherwise return a typed failure so AMPC can fail closed with pump off
- [x] Validate ET0:
  - finite numeric value
  - non-negative
  - converted to per-step value with `ET0_step = ET0_hour * step_seconds / 3600`
- [x] Do not hardcode secrets or API keys. Open-Meteo does not require a key for this first version.
- [x] Tests cover:
  - successful API response
  - cache hit
  - network/API failure with recent cache
  - network/API failure with no cache
  - invalid/non-finite ET0 response

## Completion Gates

- [x] Logic: Hourly ET0 maps deterministically to the AMPC control step.
- [x] Nghiệp vụ: The system never irrigates automatically when ET0 is required but unavailable.
- [x] Security: External HTTP errors are bounded, logged with context, and do not expose internal stack traces or secrets.
- [x] Test chạy thực tế: backend ET0 tests plus `cd Green-House\backend; python manage.py test api` pass.

## Technical Notes

- Consider a DB cache model only if needed for persistence. A smaller first version can use an existing model/state location if it survives scheduler calls safely.
- AMPC task #003 consumes this service and decides how to persist audit fields.
- Keep all timeout/retry behavior explicit; do not let the scheduler hang on network calls.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-12 | Codex | Completed ET0 service using Open-Meteo hourly FAO ET0, UTC hour cache, recent-cache fallback, typed fail-closed result, finite/non-negative validation, and backend tests |
| 2026-05-12 | Codex | Task created from FAO-56 AMPC plan |
