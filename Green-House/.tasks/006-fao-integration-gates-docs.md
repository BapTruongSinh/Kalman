---
id: "006"
title: "Run FAO-56 integration gates and update active docs after implementation"
status: "todo"
area: "qa"
agent: "@quality"
required_skills: ["quality", "docs", "planning"]
priority: "high"
created_at: "2026-05-12"
due_date: null
started_at: null
completed_at: null
prd_refs: []
blocks: []
blocked_by: ["001", "002", "003", "004", "005", "MPC-011", "MPC-012"]
---

## Description

Run the full validation pass after FAO-56 AMPC implementation and update active documentation only after the implementation is proven.

Do not update `CODEBASE_ONBOARDING.md` until the owner reviews and confirms the new flow is accepted.

## Acceptance Criteria

- [ ] Backend test gates pass:
  - `cd Green-House\backend; python manage.py test api`
  - `python manage.py check`
  - `python manage.py makemigrations --check --dry-run`
- [ ] Frontend test gates pass:
  - `cd Green-House\frontend; npm test`
  - `npm run build`
- [ ] Package test gates pass:
  - `python -m pytest Kalman\tests -q`
  - `python -m pytest MPC\tests -q`
  - `python -m compileall -q Kalman\kalman MPC\mpc Green-House\backend\api Green-House\backend\config`
- [ ] Integration scenarios are verified:
  - wet state gives no irrigation
  - dry/stressed state recommends irrigation
  - ET0 unavailable fails closed
  - invalid FAO config is rejected
  - another user's greenhouse is not accessible
  - actuator is not called unless AUTO + enabled + safe
- [ ] Update active docs after code is accepted:
  - `MPC/docs/technical/CONFIG.md`
  - `MPC/docs/technical/API.md`
  - `MPC/docs/technical/VALIDATION.md`
  - `Green-House/docs/technical/AMPC_MODELING_HANDOFF.md`
  - user-facing docs if UI fields changed
- [ ] Leave `Green-House/docs/technical/CODEBASE_ONBOARDING.md` unchanged until owner approval, then update it in a follow-up doc task or explicit approval step.
- [ ] Review memory records final verification evidence and residual risks.

## Completion Gates

- [ ] Logic: All code paths use the same FAO formulas and config defaults.
- [ ] Nghiệp vụ: The final behavior matches the accepted plan and no longer controls irrigation through legacy low/high percent bands.
- [ ] Security: Auth/ownership/fail-closed actuator behavior is covered by tests.
- [ ] Test chạy thực tế: All commands above are run and their results are recorded in this task's History.

## Technical Notes

- This task is last by design.
- If MySQL is unavailable, record the blocker and do not mark the task complete.
- If onboarding docs need updating, wait for user approval per project rule.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-12 | Codex | Task created from FAO-56 AMPC plan |
