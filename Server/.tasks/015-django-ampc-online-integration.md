---
id: "015"
title: "Implement Django AMPC online integration"
status: "completed"
area: "backend"
agent: "@backend-developer"
required_skill: "backend"
supporting_skills:
  - "planning"
  - "database"
  - "quality"
  - "docs"
  - "backend-security-coder"
  - "backend-architect"
  - "api-design-principles"
  - "api-security-best-practices"
  - "business-analyst"
  - "acceptance-orchestrator"
  - "understand"
priority: "high"
created_at: "2026-05-09"
due_date: null
started_at: "2026-05-09"
completed_at: "2026-05-09"
prd_refs: ["FR-025", "FR-026", "FR-027"]
blocks: []
blocked_by: ["014"]
---

## Description

Triển khai luồng AMPC online trong Django để dự án chuyển từ demo/CLI sang luồng production dùng được cho business thật.

Luồng bắt buộc:

```text
authenticated user + greenhouse_id
  -> verify greenhouse thuộc user
  -> load ARX model mặc định từ settings.ARX_MODEL_PATH
  -> lấy latest valid Kalman state từ DB
  -> lấy crop/controller profile của greenhouse
  -> chạy AMPC có bias correction
  -> lưu prediction/recommendation/control decision
  -> trả JSON cho dashboard
  -> nếu actuator enabled thì gửi lệnh bơm theo cấu hình an toàn
```

Multi-greenhouse là scope bắt buộc của sản phẩm thực tế: một server phục vụ nhiều user, mỗi user có thể quản lý nhiều greenhouse. Mọi state, config, recommendation, prediction và actuator result phải đi theo `greenhouse_id`. Không lưu trùng `user_id` trên bảng prediction/recommendation vì `Greenhouse.owner` đã là quan hệ business sở hữu.

Task này supersede hướng cũ "multi-greenhouse out-of-scope" cho phần AMPC online production. Khi triển khai phải thêm ADR/PRD update phù hợp trước hoặc cùng lúc với code để source of truth không còn lệch.

## Business Requirements

- [x] Một user có thể có nhiều greenhouse, mỗi greenhouse có crop/controller profile riêng.
- [x] User A không thể đọc, chạy, hoặc xem recommendation của greenhouse thuộc user B.
- [x] Sensor gửi data vào Django trước; Django lưu DB; AMPC chỉ đọc state/history đã được lưu và verify từ DB.
- [x] API production không nhận `artifact`, `state-json`, `input`, hoặc `output` từ user.
- [x] `ARX/arx_model.json` là server-side artifact, load qua `settings.ARX_MODEL_PATH`.
- [x] Dashboard chỉ cần gọi endpoint theo `greenhouse_id`, không gọi CLI.
- [x] Actuator là optional theo từng greenhouse, mặc định tắt.
- [x] Mọi lỗi an toàn phải fail-closed: pump `0`, có status/reason rõ, không gửi lệnh tưới bừa.
- [x] Mỗi lần chạy AMPC phải lưu audit row gồm state source, config snapshot, predicted horizon, cost, reason, safety status, actuator result.

## Scope

### In Scope

- [x] Tạo Django models/migration cho `GreenhouseControlProfile` và `AMPCRecommendation`.
- [x] Tạo service layer `estimation/control/` để tách business logic khỏi API view.
- [x] Tạo endpoint authenticated để dashboard trigger AMPC cho một greenhouse.
- [x] Tạo endpoint GET/PATCH control profile cho website sau này load/sửa config.
- [x] Tạo endpoint latest recommendation cho dashboard.
- [x] Map `GreenhouseControlProfile` sang `mpc.ControllerConfig`.
- [x] Lấy latest valid `PipelineCycle` theo `greenhouse_id`.
- [x] Build `mpc.ControllerState` và `mpc.PlantRecord` history từ DB.
- [x] Load `mpc.plant.ARXPlantModel` từ `settings.ARX_MODEL_PATH`.
- [x] Chạy `mpc.solver.GridShootingSolver` với `mpc.adaptive.BiasCorrectedPlantModel`.
- [x] Tính `used_today_pump_seconds` từ recommendation đã lưu trong ngày.
- [x] Nếu actuator enabled, gửi command qua `mpc.actuator.HTTPActuatorClient` hoặc abstraction tương đương; không hardcode URL/token.
- [x] Viết unit/integration tests cho service, API, authorization, fail-closed, persistence và actuator branch.
- [x] Cập nhật active docs: `API.md`, `DATABASE.md`, `ARCHITECTURE.md`, `USER_GUIDE.md`, `DECISIONS.md`, `PRD.md` nếu cần để chính thức hóa multi-greenhouse production scope.
- [x] Không cập nhật `docs/technical/CODEBASE_ONBOARDING.md` cho tới khi owner review OK thay đổi #015.

### Out Of Scope

- [x] Không train lại ARX trong Django.
- [x] Không sửa file trong `ARX/` trừ khi user yêu cầu riêng.
- [x] Không dùng CLI làm production path.
- [x] Không nhận model path từ request.
- [x] Không thêm model registry.
- [x] Không làm full dashboard UI mới nếu task chưa yêu cầu màn hình; chỉ cập nhật API client/types khi cần.
- [x] Không giải quyết đầy đủ ET0/ETc/Dr nếu chưa có calibration; chỉ giữ crop/profile fields để phase sau dùng.

## Proposed Database Design

### `greenhouse_control_profiles`

Purpose: cấu hình điều khiển AMPC theo từng greenhouse.

Required fields:

- `id`
- `greenhouse_id`: one-to-one FK tới `Greenhouse`, unique, indexed.
- User-facing crop/profile:
  - `crop_name`
  - `crop_kc`
  - `target_low`
  - `target_high`
  - `pump_max_seconds`
  - `soft_daily_pump_cap_seconds`
  - `actuator_enabled`
- System/controller defaults:
  - `step_seconds`
  - `horizon_steps`
  - `pump_min_seconds`
  - `pump_grid_seconds`
  - `cost_band_violation`
  - `cost_water_use`
  - `cost_switching`
  - `cost_daily_cap_excess`
  - `cost_terminal_band_violation`
  - `adaptive_enabled`
  - `adaptive_bias_window`
  - `adaptive_max_abs_bias`
  - `safety_stale_after_seconds`
- Actuator config:
  - `actuator_url`
  - `actuator_bearer_token_env`
  - `actuator_timeout_seconds`
- `created_at`, `updated_at`

Constraints:

- `target_low < target_high`
- `pump_max_seconds > 0`
- `soft_daily_pump_cap_seconds > 0`
- `step_seconds > 0`
- `horizon_steps > 0`
- cost weights non-negative
- `actuator_bearer_token_env` stores env var name only, never token value.

### `ampc_recommendations`

Purpose: audit trail cho mỗi lần chạy AMPC và dữ liệu dashboard cần hiển thị.

Required fields:

- `id`
- `greenhouse_id`: FK tới `Greenhouse`, indexed.
- `run_id`: FK nullable tới `ExperimentRun`.
- `state_cycle_id`: FK nullable tới `PipelineCycle`.
- `mode`: default `ampc`.
- `pump_seconds`
- `step_seconds`
- `predicted_soil_moisture_json`
- `target_low`, `target_high`
- `cost`
- `safety_status`
- `reason`
- `bias_correction`
- `bias_window_count`
- `used_today_pump_seconds`
- `config_snapshot_json`
- `state_snapshot_json`
- `actuator_enabled`
- `actuator_executed`
- `actuator_status`
- `actuator_command_json`
- `actuator_http_status_code`
- `actuator_alert`
- `actuator_error`
- `created_at`

Indexes:

- `(greenhouse_id, created_at)` for latest dashboard query.
- `(greenhouse_id, safety_status)` for operational filtering.

Rollback note: migration is additive. Rolling back drops profile/recommendation tables and loses recommendation audit history.

## Backend Service Design

Create:

```text
Server/backend/estimation/control/
  __init__.py
  config.py
  state_source.py
  bias.py
  service.py
```

Main service contract:

```python
def run_ampc_for_greenhouse(
    *,
    user,
    greenhouse_id: int,
    now: datetime | None = None,
    beam_width: int = 32,
) -> AMPCRecommendation:
    ...
```

Required service behavior:

- [x] Query `Greenhouse.objects.get(id=greenhouse_id, owner=user)` or equivalent filtered queryset.
- [x] Return 404 from API when greenhouse does not exist or belongs to another user to avoid IDOR.
- [x] Return 403/fail-safe when greenhouse is inactive.
- [x] Get or create default `GreenhouseControlProfile`.
- [x] Validate profile before building controller config.
- [x] Query latest valid state with:
  - `greenhouse_id`
  - `cycle_status="ok"`
  - `preprocess_status="valid"`
  - `kf_x_posterior is not null`
  - `raw_temperature/raw_humidity/raw_light` not null
- [x] Build history from the same greenhouse, ordered by timestamp/cycle, enough for ARX min lag.
- [x] Reject stale/future samples using MPC safety config.
- [x] Build `ControllerState` from latest DB row.
- [x] Derive `last_pump_seconds` from latest stored recommendation for that greenhouse, default `0`.
- [x] Build bias state from recent residuals: `kf_x_posterior - arx_predicted`, clipped by adaptive max.
- [x] Load ARX model from `settings.ARX_MODEL_PATH`; never accept request path.
- [x] Run AMPC and persist both success and fail-closed results.
- [x] Keep service testable without HTTP by injecting fake actuator client and fake clock where needed.

## API Design

Add routes under existing estimation API:

```http
POST /api/greenhouses/{greenhouse_id}/ampc/recommendations/
GET  /api/greenhouses/{greenhouse_id}/ampc/recommendations/latest/
GET  /api/greenhouses/{greenhouse_id}/control-profile/
PATCH /api/greenhouses/{greenhouse_id}/control-profile/
```

Required auth:

- All AMPC/control-profile endpoints require authentication in every environment.
- Object-level authorization must use `Greenhouse.owner`.

POST body:

```json
{}
```

Response shape:

```json
{
  "success": true,
  "data": {
    "id": 12,
    "greenhouse_id": 3,
    "mode": "ampc",
    "state_cycle_id": 105121,
    "run_id": 7,
    "pump_seconds": 30.0,
    "step_seconds": 300,
    "predicted_soil_moisture": [55.2, 56.1],
    "target_band": {"low": 55.0, "high": 65.0},
    "cost": 12.4,
    "safety_status": "safe",
    "reason": "below_target_margin",
    "bias_correction": 0.3,
    "used_today_pump_seconds": 120.0,
    "actuator": {
      "enabled": false,
      "executed": false,
      "status": "disabled",
      "command": null,
      "alert": null,
      "error": null
    },
    "created_at": "2026-05-09T10:00:00Z"
  },
  "error": null
}
```

Error response shape:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "state_unavailable",
    "message": "No valid Kalman state is available for this greenhouse.",
    "details": {},
    "trace_id": "..."
  }
}
```

Profile PATCH allowed fields:

- `crop_name`
- `crop_kc`
- `target_low`
- `target_high`
- `pump_max_seconds`
- `soft_daily_pump_cap_seconds`
- `actuator_enabled`
- actuator URL/env fields only if current security decision allows operator-level config from API.

Do not mass-assign request body into model. Serializer must explicitly whitelist fields.

## Security Requirements

- [x] Auth required for every endpoint in this task.
- [x] Enforce object-level auth before any DB state read, solver run, persistence or actuator call.
- [x] Return 404 for cross-user greenhouse lookup unless an existing project convention requires 403.
- [x] Do not expose `settings.ARX_MODEL_PATH` in API response.
- [x] Do not accept artifact/model path from request.
- [x] Do not expose actuator token or token env value.
- [x] Do not log token, raw Authorization header or secrets.
- [x] Validate actuator URL to avoid SSRF. If no allowlist exists, initial implementation must restrict actuator config to server/operator controlled values.
- [x] Fail-closed with pump `0` for missing state, stale/future state, insufficient history, model load error, solver error, unsafe recommendation, actuator config error, and HTTP timeout/error; when actuator is disabled, do not send HTTP and keep the recommendation as recommendation-only.
- [x] Use ORM queries only; no raw SQL unless a migration requires it and is reviewed.
- [x] Add regression test proving injected/fake actuator cannot bypass invalid actuator config.

## Implementation Checklist

1. [x] Re-read preflight files before starting code:
   - `.claude/CLAUDE.md`
   - `.claude/.claude/rules/*.md`
   - `.claude/.claude/review/REVIEW.md`
   - `Kalman/CLAUDE.md`
   - `Server/docs/technical/CODEBASE_ONBOARDING.md`
   - `Kalman/TODO.md`
   - this task file
2. [x] Use skills before code:
   - local `backend`, `database`, `quality`, `docs`, `planning`
   - `backend-security-coder`
   - codex `backend-architect`, `api-design-principles`, `api-security-best-practices`, `business-analyst`, `acceptance-orchestrator`
   - agents `understand` for code tracing; if full graph cannot run, document why and do targeted code tracing.
3. [x] Add ADR that production AMPC online is multi-user/multi-greenhouse and supersedes old v1 out-of-scope language.
4. [x] Decide dependency strategy for `greenhouse-mpc` package:
   - preferred: install package from `MPC/` as editable/dev dependency or internal wheel.
   - forbidden: runtime `sys.path` hacks in Django code.
5. [x] Add models and Django migration.
6. [x] Add profile/config mapper.
7. [x] Add state/history source module.
8. [x] Add bias builder module.
9. [x] Add AMPC service.
10. [x] Add serializers.
11. [x] Add API views and URL patterns.
12. [x] Add tests.
13. [x] Update docs.
14. [x] Run migrations/checks/tests.
15. [x] Update TODO/task status, review memory and report evidence.

## Test Plan

### Unit Tests

- [x] `profile_to_controller_config()` maps default profile to expected `ControllerConfig`.
- [x] Profile validation rejects `target_low >= target_high`.
- [x] Profile validation rejects non-positive pump max, daily cap, step seconds and horizon.
- [x] Cost weights are non-negative.
- [x] `latest_state_for_greenhouse()` selects newest valid cycle for the correct greenhouse.
- [x] State lookup ignores invalid/skipped/error cycles.
- [x] State lookup rejects missing temperature/humidity/light.
- [x] State lookup rejects stale sample.
- [x] State lookup rejects future sample outside clock skew.
- [x] History builder returns causal ordered `PlantRecord` list for the same greenhouse only.
- [x] Bias builder uses recent residuals and clips by `adaptive_max_abs_bias`.
- [x] `used_today_pump_seconds` sums only same greenhouse and same day.
- [x] AMPC service happy path persists recommendation.
- [x] AMPC service missing state persists fail-closed recommendation.
- [x] AMPC service insufficient history persists fail-closed recommendation.
- [x] AMPC service ARX load error persists fail-closed recommendation.
- [x] Actuator disabled path does not call actuator client.
- [x] Actuator enabled but config invalid fails closed and does not call HTTP.
- [x] Actuator enabled with fake valid client records `executed=true` only when recommendation is safe.
- [x] Unsafe recommendation with actuator enabled does not call actuator and persists `executed=false`.
- [x] Actuator HTTP failure records fail-closed status and error without leaking secrets.

### API Integration Tests

- [x] Unauthenticated AMPC POST returns `401`.
- [x] User calling another user's greenhouse returns `404` or project-standard `403` and creates no recommendation.
- [x] Owner calling active greenhouse with valid state returns `201` and creates one recommendation.
- [x] Inactive greenhouse returns `403` and does not call actuator.
- [x] No valid state returns structured error/fail-closed status.
- [x] Latest recommendation endpoint returns newest row for requested greenhouse only.
- [x] Profile GET creates default profile if missing.
- [x] Profile PATCH updates only allowed fields.
- [x] Profile PATCH rejects invalid numeric ranges.
- [x] Endpoint response never includes model path, token env value or raw token.

### Regression And Smoke Gates

Run from `Server/backend`:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py migrate --check
python -m pytest estimation\tests -q
python -m compileall -q estimation
```

If task adds `greenhouse-mpc` as an installed dependency, also run from repo root:

```powershell
python -m pytest MPC\tests -q
python -m compileall -q MPC\mpc
```

## Acceptance Criteria

- [x] `Kalman/TODO.md` and this task file stay synced through start/completion.
- [x] Multi-greenhouse is documented as required production scope in active source-of-truth docs/ADR.
- [x] Endpoint AMPC accepts authenticated user + `greenhouse_id`, with no artifact/state/input/output path parameters.
- [x] Endpoint verifies greenhouse ownership before reading state or running solver.
- [x] Control profile exists per greenhouse and maps to MPC config.
- [x] Latest valid Kalman state/history are read from DB by `greenhouse_id`.
- [x] ARX model is loaded from `settings.ARX_MODEL_PATH`.
- [x] AMPC uses bias correction, not static MPC only.
- [x] Recommendation/prediction is persisted with greenhouse scope and audit snapshots.
- [x] Dashboard JSON includes pump seconds, predicted horizon, target band, cost, safety status, reason and actuator result.
- [x] Actuator command only sends when enabled and config is valid.
- [x] All safety failures return or persist pump `0` with clear reason/status.
- [x] Unit and integration tests cover business, authz, state validation, AMPC persistence and actuator fail-closed behavior.
- [x] Active docs are updated except `CODEBASE_ONBOARDING.md`, which waits for owner review OK.

## Completion Gates

### Logic

- [x] Service layer can be called without HTTP and has deterministic behavior with injected `now`.
- [x] State, history, recommendation and actuator result all use the same `greenhouse_id`.
- [x] No code path can run AMPC using request-supplied artifact path.
- [x] No code path reads state before ownership is verified.

### Nghiệp vụ

- [x] Supports one server, many users, many greenhouses per user.
- [x] A greenhouse has its own crop/controller profile.
- [x] Dashboard can run and display AMPC per greenhouse.
- [x] Recommendation rows are useful as business audit history.

### Security

- [x] Auth/authz tests pass for unauthenticated, cross-user and owner cases.
- [x] Token/model path/secrets are not returned or logged.
- [x] Actuator URL/token handling passes SSRF/secrets review for the chosen initial scope.
- [x] Fake/injected actuator cannot bypass invalid actuator config.

### Test chạy thực tế

- [x] Django migration checks pass.
- [x] Django system check passes.
- [x] Backend pytest suite passes.
- [x] MPC package tests pass if imported as dependency.
- [x] A smoke test creates an AMPC recommendation row for a seeded greenhouse/state.

## Completion Evidence

### Logic

- Service entrypoint `run_ampc_for_greenhouse()` can run without HTTP and accepts injected `now`, `beam_width`, actuator client, and command ID factory for deterministic tests.
- `_owned_greenhouse(user, greenhouse_id)` runs before latest-state/history/model/solver work; cross-user API test returns 404 and creates no recommendation.
- AMPC model path is always `settings.ARX_MODEL_PATH`; POST body must be `{}` and cannot carry artifact/state/input/output paths.
- State/history/recommendation/actuator audit rows all use the same `greenhouse_id`.

### Nghiep vu

- `GreenhouseControlProfile` is one-to-one per greenhouse and stores crop/target/pump/profile defaults.
- `AMPCRecommendation` persists the audit trail for safe and fail-closed outcomes, including config snapshot, state snapshot, predicted horizon, cost, reason, safety status, bias, daily usage, and actuator result.
- Dashboard API client/types include control profile, run recommendation, and latest recommendation contracts.
- Active docs record multi-user/multi-greenhouse AMPC online as production scope through ADR-006.

### Security

- AMPC/control endpoints force auth in every environment and use `Greenhouse.owner` for object authorization.
- Serializer response excludes `settings.ARX_MODEL_PATH`, raw actuator tokens, token env names, `config_snapshot_json`, and `state_snapshot_json`.
- Actuator URL validation rejects local/private/link-local/multicast/reserved hosts; token value is loaded only from environment.
- Fake/injected actuator clients cannot bypass invalid config because service validates `HTTPActuatorClient.from_config()` before using injection.

### Test chay thuc te

- `python manage.py makemigrations --check --dry-run` -> no changes detected.
- `python manage.py check` -> no issues.
- `python manage.py migrate --check` -> pass.
- `python -m pytest estimation\tests -q` -> 108 passed.
- `python -m compileall -q estimation` -> pass.
- `python -m pytest MPC\tests -q` -> 80 passed.
- `python -m compileall -q MPC\mpc` -> pass.
- `npm test -- --run` -> 5 files / 34 tests passed.
- `npm run build` -> pass; Vite chunk-size warning only.
- AMPC smoke test created one recommendation row for seeded greenhouse/state inside a transaction and rolled back successfully.
- `git diff --check` -> no whitespace errors; Windows LF/CRLF warnings only.

### Self Review

- Skills used/rechecked: local `backend`, `database`, `quality`, `docs`, `planning`; Codex `backend-security-coder`, `backend-architect`, `api-design-principles`, `api-security-best-practices`, `business-analyst`, `acceptance-orchestrator`.
- `understand` skill file was not present at `C:\Users\ADMIN\.codex\skills\understand\SKILL.md`, but the previously requested understand graph exists at `.understand-anything/knowledge-graph.json` and was used for targeted tracing; metadata shows 269 analyzed files.
- Final self-review grep checked auth/ownership ordering, request path/token exposure, actuator config handling, and generated files. No open runtime findings remain.
- `Server/docs/technical/CODEBASE_ONBOARDING.md` intentionally remains unchanged until owner review OK, per project rule.

## Risks And Notes

- `MPC/` is a sibling package named `greenhouse-mpc`. Backend integration must use a real packaging/dependency strategy, not CLI calls.
- Existing `CODEBASE_ONBOARDING.md` currently describes AMPC as boundary/prototype and must not be treated as final for #015. Sync it only after owner review.
- Existing dashboard GET API can be unauthenticated in development via settings, but AMPC/control endpoints must always force auth.
- Actuator config has SSRF risk if arbitrary URL is user-editable. Initial task should prefer operator/server-controlled actuator settings unless an allowlist is implemented.
- If MySQL has no valid greenhouse state, service must persist or return a clear fail-closed result rather than inventing sensor values.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-05-09 | human | Clarified production requirement: multi-user, multi-greenhouse, Django endpoint/service runs AMPC by authenticated user + greenhouse_id |
| 2026-05-09 | Codex | Created detailed task from approved plan; kept status `todo` because implementation has not started |
| 2026-05-09 | Codex | Started implementation after rereading rules, CLAUDE files, review memory, onboarding, TODO, task file, and required skills |
| 2026-05-09 | Codex | Completed implementation, validation gates, smoke test, self-review, TODO sync, and evidence recording; kept `CODEBASE_ONBOARDING.md` unchanged until owner review OK |
| 2026-05-09 | Codex | Fixed post-review issues: unsafe recommendations no longer call/execute actuator, dashboard API client accepts auth/CSRF options, docs/tests updated |
