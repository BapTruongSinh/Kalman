---
id: "006"
title: "Run FAO-56 integration gates and update active docs after implementation"
status: "completed"
area: "qa"
agent: "@quality"
required_skills: ["quality", "docs", "planning"]
priority: "high"
created_at: "2026-05-12"
due_date: null
started_at: "2026-05-12"
completed_at: "2026-05-12"
prd_refs: []
blocks: []
blocked_by: ["001", "002", "003", "004", "005", "MPC-011", "MPC-012"]
---

## Description

Run the full validation pass after FAO-56 AMPC implementation and update active documentation only after the implementation is proven.

Do not update `CODEBASE_ONBOARDING.md` until the owner reviews and confirms the new flow is accepted.

## Acceptance Criteria

- [x] Backend test gates pass:
  - `cd Green-House\backend; python manage.py test api`
  - `python manage.py check`
  - `python manage.py makemigrations --check --dry-run`
- [x] Frontend test gates pass:
  - `cd Green-House\frontend; npm test`
  - `npm run build`
- [x] Package test gates pass:
  - `python -m pytest Kalman\tests -q`
  - `python -m pytest MPC\tests -q`
  - `python -m compileall -q Kalman\kalman MPC\mpc Green-House\backend\api Green-House\backend\config`
- [x] Integration scenarios are verified:
  - wet state gives no irrigation
  - dry/stressed state recommends irrigation
  - ET0 unavailable fails closed
  - invalid FAO config is rejected
  - another user's greenhouse is not accessible
  - actuator is not called unless AUTO + enabled + safe
- [x] Update active docs after code is accepted:
  - `MPC/docs/technical/CONFIG.md`
  - `MPC/docs/technical/API.md`
  - `MPC/docs/technical/VALIDATION.md`
  - `Green-House/docs/technical/AMPC_MODELING_HANDOFF.md`
  - user-facing docs if UI fields changed
- [x] Leave `Green-House/docs/technical/CODEBASE_ONBOARDING.md` unchanged until owner approval, then update it in a follow-up doc task or explicit approval step.
- [x] Review memory records final verification evidence and residual risks.

## Completion Gates

- [x] Logic: All code paths use the same FAO formulas and config defaults.
- [x] Nghiệp vụ: The final behavior matches the accepted plan and no longer controls irrigation through legacy low/high percent bands.
- [x] Security: Auth/ownership/fail-closed actuator behavior is covered by tests.
- [x] Test chạy thực tế: All commands above are run and their results are recorded in this task's History.

## Technical Notes

- This task is last by design.
- If MySQL is unavailable, record the blocker and do not mark the task complete.
- If onboarding docs need updating, wait for user approval per project rule.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-12 | Codex | Task created from FAO-56 AMPC plan |
| 2026-05-12 | Codex | Started final FAO-56 integration validation and active-doc sync. |
| 2026-05-12 | Codex | Ran final gates: backend `python manage.py test api -v 1 --noinput` -> 31 passed; `python manage.py check` OK; `python manage.py makemigrations --check --dry-run` no changes; applied local DB migration `api.0010_add_fao56_control_profile_config`, then `python manage.py migrate --check` OK; `python -m pip install -r requirements-local.txt --dry-run` OK; frontend `npm test` OK and `npm run build` OK; `python -m pytest Kalman\tests -q` -> 15 passed; `python -m pytest MPC\tests -q` -> 117 passed; `python -m compileall -q Kalman\kalman MPC\mpc Green-House\backend\api Green-House\backend\config` OK; `git diff --check` clean apart from CRLF warnings. |
| 2026-05-12 | Codex | Updated active docs: MPC config/API/validation, Green-House AMPC handoff, and Green-House user guide. Left `Green-House/docs/technical/CODEBASE_ONBOARDING.md` unchanged per owner-approval rule. |
