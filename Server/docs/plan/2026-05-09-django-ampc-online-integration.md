# Plan: Django AMPC Online Integration Cho Production Multi-Greenhouse

## Mục Tiêu

Biến luồng AMPC từ CLI/demo thành luồng production trong Django:

```text
Authenticated user + greenhouse_id
  -> verify greenhouse thuộc user
  -> load ARX artifact mặc định từ settings.ARX_MODEL_PATH
  -> lấy latest valid Kalman state từ DB
  -> lấy crop/controller profile của greenhouse
  -> chạy AMPC có bias correction
  -> lưu recommendation/control decision
  -> trả JSON cho dashboard
  -> nếu actuator enabled thì gửi lệnh, nếu lỗi thì fail-closed
```

Đây là scope bắt buộc cho dự án thực tế. Một server phục vụ nhiều user; mỗi user có thể sở hữu nhiều greenhouse. Mọi state, config, prediction, recommendation và actuator command phải đi theo `greenhouse_id`. Không dùng `state-json`, không bắt user truyền `artifact`, không thêm CLI param cho production flow.

## Business Requirements Bắt Buộc

- Multi-tenant: user A không được đọc/chạy AMPC cho greenhouse của user B.
- Multi-greenhouse: một user có thể có nhiều greenhouse, mỗi greenhouse có profile/config riêng.
- Greenhouse là business aggregate chính: prediction/recommendation lưu `greenhouse_id`, user suy ra qua `Greenhouse.owner`.
- Sensor là source of truth đầu vào: sensor gửi dữ liệu lên Django, Django lưu DB, AMPC đọc từ DB.
- ARX model là server-side artifact: mặc định `ARX/arx_model.json` qua `settings.ARX_MODEL_PATH`; API không nhận path model.
- Dashboard gọi API đơn giản theo greenhouse, không gọi CLI.
- Auto actuator là optional theo config của greenhouse; default tắt.
- Fail-closed: thiếu state, state stale, thiếu history, model lỗi, actuator lỗi, token thiếu đều không được tưới bừa.
- Audit được: mỗi lần AMPC chạy phải lưu recommendation, config snapshot, state source, actuator result.

## Scope

### In Scope

- Django service `run_ampc_for_greenhouse(user, greenhouse_id, ...)`.
- Django endpoint authenticated để dashboard trigger AMPC cho một greenhouse.
- Model DB cho crop/controller profile theo greenhouse.
- Model DB cho AMPC recommendation/control decision.
- Lấy latest valid `PipelineCycle` theo `greenhouse_id`.
- Build `ControllerState` và ARX/MPC `PlantRecord` history từ DB.
- Load `ARXPlantModel` từ `settings.ARX_MODEL_PATH`.
- Dùng `GridShootingSolver` và `BiasCorrectedPlantModel` để chạy AMPC.
- Tính `used_today_pump_seconds` từ recommendation đã lưu trong ngày.
- Lưu recommendation JSON, predicted horizon, cost, safety status, reason, bias, state cycle, config snapshot.
- Nếu actuator enabled: gửi HTTP command qua MPC actuator client, không hardcode token/url.
- Nếu actuator disabled: chỉ lưu recommendation, actuator status là `disabled`.
- API trả JSON dashboard-friendly.
- Tests unit/integration cho authz, no-state, stale-state, happy path, persistence, actuator disabled/enabled/fail.
- Docs `API.md`, `DATABASE.md`, `ARCHITECTURE.md`, `USER_GUIDE.md`, ADR mới.
- Không cập nhật `CODEBASE_ONBOARDING.md` cho tới khi owner review OK.

### Out Of Scope Cho Task Này

- Không train lại ARX.
- Không sửa file trong `ARX/`.
- Không dùng CLI làm production path.
- Không làm full UI dashboard nếu chưa cần màn hình mới; chỉ cập nhật API client/types nếu có consumer.
- Không thêm model registry.
- Không giải bài toán ET0/ETc/Dr đầy đủ nếu chưa có calibration; chỉ lưu crop `kc`/profile để website và phase sau dùng.

## Kiến Trúc Đề Xuất

### 1. Database

Thêm bảng `greenhouse_control_profiles`:

- `greenhouse_id` one-to-one FK.
- User-facing crop/config:
  - `crop_name`
  - `crop_kc`
  - `target_low`
  - `target_high`
  - `pump_max_seconds`
  - `soft_daily_pump_cap_seconds`
  - `actuator_enabled`
- System/default config:
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
  - `actuator_url`
  - `actuator_bearer_token_env`
  - `actuator_timeout_seconds`
- Timestamps.
- FK `greenhouse_id` indexed/unique.
- Không lưu token thật trong DB, chỉ lưu env var name.

Thêm bảng `ampc_recommendations`:

- `greenhouse_id` FK.
- `run_id` FK nullable, lấy từ latest cycle.
- `state_cycle_id` FK nullable tới `PipelineCycle`.
- `mode`: `ampc`.
- `pump_seconds`, `step_seconds`.
- `predicted_soil_moisture_json`.
- `target_low`, `target_high`.
- `cost`.
- `safety_status`, `reason`.
- `bias_correction`, `bias_window_count`.
- `used_today_pump_seconds`.
- `config_snapshot_json`.
- `state_snapshot_json`.
- `actuator_enabled`.
- `actuator_executed`.
- `actuator_status`.
- `actuator_command_json`.
- `actuator_http_status_code`.
- `actuator_alert`.
- `actuator_error`.
- `created_at`.

Indexes:

- `idx_ampc_greenhouse_created` on `(greenhouse_id, created_at)`.
- `idx_ampc_greenhouse_status` on `(greenhouse_id, safety_status)`.
- `idx_profiles_greenhouse` unique one-to-one.

Rollback risk: additive migration, low risk. Dropping these new tables later is destructive for recommendation audit history, so rollback note must state data loss.

### 2. Backend Service

Tạo package/module trong Kalman backend:

```text
estimation/control/
  __init__.py
  config.py          # map GreenhouseControlProfile -> MPC ControllerConfig
  state_source.py    # latest valid state/history from PipelineCycle
  bias.py            # build BiasState from recent residuals
  service.py         # run_ampc_for_greenhouse()
```

Service contract:

```python
run_ampc_for_greenhouse(
    *,
    user,
    greenhouse_id: int,
    now: datetime | None = None,
    beam_width: int = 32,
) -> AMPCRecommendation
```

Logic:

1. Query `Greenhouse.objects.select_related("control_profile").get(id=greenhouse_id, owner=user)`.
2. Nếu không có greenhouse hoặc không thuộc user: 404 để tránh IDOR.
3. Nếu greenhouse inactive: 403.
4. Lấy hoặc tạo default `GreenhouseControlProfile`.
5. Lấy latest valid state:
   - `greenhouse_id`
   - `cycle_status="ok"`
   - `preprocess_status="valid"`
   - `kf_x_posterior is not null`
   - `raw_temperature`, `raw_humidity`, `raw_light` không null.
6. Lấy history đủ cho ARX `min_history_len`.
7. Load `ARXPlantModel.load_artifact(settings.ARX_MODEL_PATH, pump_limits=config.pump)`.
8. Build `ControllerState`:
   - `timestamp = latest.sample_ts`
   - `kf_x_posterior`
   - raw sensor context
   - `last_pump_seconds` từ recommendation gần nhất hoặc 0.
   - `run_id = latest.run_id`
9. Build AMPC bias:
   - residual = `kf_x_posterior - arx_predicted`
   - dùng các cycle gần đây, valid, có đủ ARX và Kalman.
   - clip theo `adaptive_max_abs_bias`.
10. Chạy `GridShootingSolver` với `BiasCorrectedPlantModel`.
11. Nếu lỗi state/model/history/stale: tạo recommendation fail-closed pump 0, vẫn lưu DB.
12. Nếu profile actuator disabled: không gửi HTTP, lưu `actuator_status="disabled"`.
13. Nếu actuator enabled:
   - validate URL/token env qua `HTTPActuatorClient.from_config`.
   - gửi command chỉ khi recommendation `safe`.
   - nếu recommendation unsafe hoặc actuator lỗi: command pump 0.
   - không trả token trong response/log.
14. Lưu `AMPCRecommendation`.
15. Trả object cho serializer/API.

### 3. API Endpoint

Endpoint chính:

```http
POST /api/greenhouses/{greenhouse_id}/ampc/recommendations/
Authorization: Token <token> hoặc session auth
```

Request body: optional, mặc định rỗng.

```json
{}
```

Response `201 Created`:

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

Error shape cho endpoint mới:

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

Endpoint phụ cho dashboard/config website:

```http
GET /api/greenhouses/{greenhouse_id}/control-profile/
PATCH /api/greenhouses/{greenhouse_id}/control-profile/
GET /api/greenhouses/{greenhouse_id}/ampc/recommendations/latest/
```

PATCH chỉ nhận field user-facing và actuator config an toàn. Không nhận weight nếu UI chưa cần; weight/system defaults có thể giữ server-side.

### 4. Dashboard/API Contract

- Dashboard chọn greenhouse.
- Dashboard gọi `POST /api/greenhouses/{id}/ampc/recommendations/` để chạy AMPC.
- Dashboard hiển thị:
  - pump seconds
  - predicted horizon
  - safety status
  - reason
  - actuator status
  - timestamp
- Dashboard không gửi artifact/state-json/input/output.
- Nếu profile chưa có, backend tự tạo profile default và trả profile để UI hiển thị.

## Security Gates

- Auth required cho toàn bộ endpoint AMPC.
- Object-level auth bằng `Greenhouse.owner`.
- Không expose artifact path tuyệt đối.
- Không expose actuator token.
- Không nhận actuator token raw từ API.
- Không cho user override `ARX_MODEL_PATH`.
- Fail-closed pump 0 khi:
  - state missing
  - state stale/future
  - insufficient history
  - ARX load lỗi
  - solver/model lỗi
  - actuator disabled/config lỗi/http lỗi.
- Log phải có greenhouse_id, recommendation_id, safety_status; không log token.

## Test Plan

### Unit Tests

- `profile_to_controller_config()` map đúng defaults và user-facing fields.
- Invalid profile values raise validation error hoặc bị serializer chặn.
- `latest_state_for_greenhouse()` chọn đúng latest valid cycle.
- Missing temperature/humidity/light bị state unavailable.
- Bias builder dùng recent residuals, clip theo max_abs_bias.
- `run_ampc_for_greenhouse()` happy path lưu recommendation.
- Insufficient history lưu fail-closed recommendation.
- Stale sample lưu fail-closed recommendation.
- Actuator disabled không gọi HTTP.
- Actuator enabled thiếu token fail-closed và không gọi HTTP.

### API Integration Tests

- Unauthenticated POST trả 401.
- User khác gọi greenhouse không thuộc mình trả 404 hoặc 403, không tạo recommendation.
- Owner gọi greenhouse active có state valid trả 201 và tạo DB row.
- Greenhouse inactive trả 403.
- No valid state trả error có code rõ, không actuator.
- Latest endpoint trả recommendation mới nhất của đúng greenhouse.
- Profile GET tạo default nếu chưa có.
- Profile PATCH chỉ update allowed fields, reject invalid target band/pump cap.

### Regression/Smoke Gates

```powershell
cd Server/backend
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py migrate
python -m pytest estimation/tests -q
python -m compileall -q estimation
```

Nếu backend import trực tiếp package `mpc`, chạy thêm:

```powershell
python -m pytest ..\..\MPC\tests -q
python -m compileall -q ..\..\MPC\mpc
```

## Implementation Steps

1. Tạo task #015 trong `Kalman/TODO.md` và `Kalman/.tasks/015-django-ampc-online-integration.md`.
2. Thêm ADR-006: production multi-user multi-greenhouse AMPC runtime supersedes old "multi-greenhouse out-of-scope" wording.
3. Thêm dependency/import strategy cho `greenhouse-mpc`:
   - Dev: backend có thể install editable `../../MPC`.
   - Production: build/install wheel nội bộ, không dùng CLI.
4. Thêm models + migration:
   - `GreenhouseControlProfile`
   - `AMPCRecommendation`
5. Thêm `estimation/control/` service layer.
6. Thêm serializers/API views/urls cho:
   - profile GET/PATCH
   - AMPC run POST
   - latest recommendation GET
7. Thêm tests theo test plan.
8. Cập nhật docs:
   - `API.md`
   - `DATABASE.md`
   - `ARCHITECTURE.md`
   - `USER_GUIDE.md`
   - `DECISIONS.md`
   - không cập nhật `CODEBASE_ONBOARDING.md` cho tới khi user review OK.
9. Chạy migration và validation gates.
10. Cập nhật TODO/task/review memory.

## Acceptance Criteria

- [ ] Một user có thể có nhiều greenhouse, mỗi greenhouse có control profile riêng.
- [ ] Endpoint AMPC không nhận artifact/state-json/input/output.
- [ ] Endpoint AMPC verify greenhouse thuộc user trước khi đọc/chạy/lưu.
- [ ] Service lấy latest valid Kalman state và history từ DB theo `greenhouse_id`.
- [ ] Service load ARX model mặc định từ `settings.ARX_MODEL_PATH`.
- [ ] Service chạy AMPC có bias correction, không chỉ MPC tĩnh.
- [ ] Recommendation được lưu vào DB với `greenhouse_id`, state source, config snapshot, predicted horizon, safety status, actuator result.
- [ ] Actuator chỉ gửi khi profile bật và config/token hợp lệ.
- [ ] Mọi lỗi an toàn đều fail-closed pump 0 và có error/status rõ.
- [ ] Dashboard có JSON contract đủ để hiển thị recommendation và actuator status.
- [ ] Tests pass và docs active được cập nhật.

## Rủi Ro Và Cách Xử Lý

- Import `MPC/mpc` vào Django có thể chưa được cài trong backend env.
  - Xử lý: thêm dependency strategy rõ trong requirements/dev setup; không import bằng `sys.path` hack.
- `PipelineCycle` cũ có thể thiếu raw temperature/humidity/light.
  - Xử lý: service fail-closed `state_unavailable` thay vì tự bịa disturbance.
- ARX history có thể chưa đủ.
  - Xử lý: lưu fail-closed recommendation `model_error/history_too_short`, dashboard thấy lý do.
- Actuator HTTP có SSRF risk nếu user nhập URL tùy ý.
  - Xử lý: giai đoạn đầu chỉ admin/operator cấu hình URL hoặc dùng allowlist/domain validation; token chỉ từ env.
- Tính `used_today_pump_seconds` theo timezone.
  - Xử lý: dùng timezone-aware `created_at`; ngày mặc định theo Django timezone. Nếu sau này greenhouse có timezone riêng thì thêm field.

