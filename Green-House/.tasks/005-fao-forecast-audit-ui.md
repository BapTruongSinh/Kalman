---
id: "005"
title: "Show FAO audit data in forecast/dashboard without breaking percent chart"
status: "todo"
area: "frontend"
agent: "@builder"
required_skills: ["frontend", "quality", "docs"]
priority: "normal"
created_at: "2026-05-12"
due_date: null
started_at: null
completed_at: null
prd_refs: []
blocks: ["006"]
blocked_by: ["003"]
---

## Description

Expose the new FAO AMPC audit fields in the forecast/dashboard view while keeping the current predicted soil moisture percent chart stable.

The user-facing chart remains sensor percent. Physical fields are shown as audit/control diagnostics.

## Acceptance Criteria

- [ ] Extend frontend API types for FAO audit data returned by recommendation endpoints.
- [ ] Keep existing forecast line based on `predicted_soil_moisture` percent.
- [ ] Add compact diagnostics for:
  - `Dr`
  - `TAW`
  - `RAW`
  - `Ks`
  - `ET0_step`
  - `ETc_adj`
  - `irrigation_depth_mm`
- [ ] Show stress status:
  - safe zone when `Dr <= RAW`
  - water stress when `Dr > RAW`
  - wet/no-irrigation state when `Dr = 0`
- [ ] Do not show raw internal stack traces or confusing backend error details.
- [ ] Frontend tests cover rendering with and without FAO audit fields.

## Completion Gates

- [ ] Logic: Percent chart remains compatible with old response shape; diagnostics are optional and null-safe.
- [ ] Nghiệp vụ: UI explains control status through physical FAO values without implying `55% sensor = theta 0.55`.
- [ ] Security: Error display is safe and does not leak backend internals.
- [ ] Test chạy thực tế: `cd Green-House\frontend; npm test` and `npm run build` pass.

## Technical Notes

- Relevant files:
  - `Green-House/frontend/src/app/components/ForecastPage.tsx`
  - `Green-House/frontend/src/app/api/endpoints.ts`
- This task depends on backend audit fields from task #003.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-12 | Codex | Task created from FAO-56 AMPC plan |
