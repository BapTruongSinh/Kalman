---
id: "004"
title: "Add FAO config controls to frontend auto settings"
status: "done"
area: "frontend"
agent: "@builder"
required_skills: ["frontend", "quality", "docs"]
priority: "high"
created_at: "2026-05-12"
due_date: null
started_at: "2026-05-12"
completed_at: "2026-05-12"
prd_refs: []
blocks: ["006"]
blocked_by: ["001"]
---

## Description

Update the frontend auto settings UI so users can configure the FAO physical inputs saved by Green-House task #001.

This task does not change the forecast chart yet.

## Acceptance Criteria

- [x] Update frontend API types in `Green-House/frontend/src/app/api/endpoints.ts` for all new FAO config fields.
- [x] Update `AutoSettings.tsx` to show controls for:
  - crop coefficient `Kc`
  - soil type select box
  - root depth `Zr`
  - pump flow `Q`
  - irrigation area `A`
  - pump efficiency `eta`
  - coordinates if the UI already has a suitable place, otherwise keep default backend values
- [x] Soil type select applies presets:
  - sand
  - light loam
  - loam
  - clay loam
- [x] User can still edit physical soil values after choosing a preset if backend contract allows it.
- [x] UI makes clear through field labels/units that sensor percent is not volumetric `theta`.
- [x] Form handles loading, error, and save states.
- [x] Existing auto settings values still load/save correctly.
- [x] Frontend tests cover:
  - fields render from API response
  - soil preset changes the expected physical values
  - save payload includes FAO fields
  - API validation error is displayed

## Completion Gates

- [x] Logic: UI payload names match backend serializer fields exactly.
- [x] Nghiệp vụ: Defaults and presets match the accepted plan.
- [x] Security: User input is validated client-side where practical and server-side remains authoritative.
- [x] Test chạy thực tế: `cd Green-House\frontend; npm test` and `npm run build` pass.

## Technical Notes

- Relevant files:
  - `Green-House/frontend/src/app/api/endpoints.ts`
  - `Green-House/frontend/src/app/components/AutoSettings.tsx`
  - frontend test files near current component tests
- Keep layout dense and operational; this is a settings surface, not a landing page.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-12 | Codex | Task created from FAO-56 AMPC plan |
| 2026-05-12 | Codex | Implemented frontend FAO controls, soil presets, client validation, save payload builder, smoke coverage, and handoff docs. |
| 2026-05-12 | Codex | Fixed review findings: client and backend now reject invalid runtime config values, and frontend smoke test executes helper behavior plus server-renders the loaded settings form. |
