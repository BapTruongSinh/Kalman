---
id: "004"
title: "Add FAO config controls to frontend auto settings"
status: "todo"
area: "frontend"
agent: "@builder"
required_skills: ["frontend", "quality", "docs"]
priority: "high"
created_at: "2026-05-12"
due_date: null
started_at: null
completed_at: null
prd_refs: []
blocks: ["006"]
blocked_by: ["001"]
---

## Description

Update the frontend auto settings UI so users can configure the FAO physical inputs saved by Green-House task #001.

This task does not change the forecast chart yet.

## Acceptance Criteria

- [ ] Update frontend API types in `Green-House/frontend/src/app/api/endpoints.ts` for all new FAO config fields.
- [ ] Update `AutoSettings.tsx` to show controls for:
  - crop coefficient `Kc`
  - soil type select box
  - root depth `Zr`
  - pump flow `Q`
  - irrigation area `A`
  - pump efficiency `eta`
  - coordinates if the UI already has a suitable place, otherwise keep default backend values
- [ ] Soil type select applies presets:
  - sand
  - light loam
  - loam
  - clay loam
- [ ] User can still edit physical soil values after choosing a preset if backend contract allows it.
- [ ] UI makes clear through field labels/units that sensor percent is not volumetric `theta`.
- [ ] Form handles loading, error, and save states.
- [ ] Existing auto settings values still load/save correctly.
- [ ] Frontend tests cover:
  - fields render from API response
  - soil preset changes the expected physical values
  - save payload includes FAO fields
  - API validation error is displayed

## Completion Gates

- [ ] Logic: UI payload names match backend serializer fields exactly.
- [ ] Nghiệp vụ: Defaults and presets match the accepted plan.
- [ ] Security: User input is validated client-side where practical and server-side remains authoritative.
- [ ] Test chạy thực tế: `cd Green-House\frontend; npm test` and `npm run build` pass.

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
