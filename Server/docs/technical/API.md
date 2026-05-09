<!--
DOCUMENT METADATA
Owner: @backend-developer
Update trigger: Any API endpoint or pipeline contract is added, modified, or removed
Read by: @frontend-developer and @qa-engineer
-->

# API Reference

> **Base URL (dev)**: `http://127.0.0.1:8000/api`
> **Authentication**: With `DJANGO_ENV=production`, dashboard `GET` endpoints default to **IsAuthenticated** unless you set `DASHBOARD_REQUIRE_AUTH=false` explicitly. In `development`, they default to **AllowAny** unless `DASHBOARD_REQUIRE_AUTH=true`. The live ingestion endpoint at `/api/ingest/samples/` always requires a **DRF Token** (`Authorization: Token <token>`). AMPC/control-profile endpoints always require authentication in every environment.
> **Content-Type**: `application/json`
> **Last updated**: 2026-05-09

**Security / deployment**: With `DJANGO_ENV=production`, `DJANGO_SECRET_KEY` is **required** (the process will not start without it). Dashboard read APIs default to **authenticated** users unless `DASHBOARD_REQUIRE_AUTH=false`. Production also enables `SecurityMiddleware`, CSRF, `XFrameOptionsMiddleware`, session middleware, and secure cookie / HSTS / SSL-redirect flags (see `.env.example`). `CORS_ALLOWED_ORIGINS` accepts comma- or whitespace-separated URLs. Run `python manage.py check --deploy` after exporting production env vars.

**Pipeline semantics** (ARX vs Kalman roles, innovation/residual meaning, adaptive `R`, evaluation gates, AMPC contracts): see [`METHODOLOGY_V1.md`](./METHODOLOGY_V1.md). This file focuses on **HTTP shapes** and field lists.

---

## Live Ingestion Endpoint (Task #010)

### `POST /api/ingest/samples/`

Accept one live sensor reading from a device and run a single Adaptive Kalman step.

Runtime prediction source: the endpoint loads a server-side cached ARX adapter from `settings.ARX_MODEL_PATH` (default repo-root `ARX/arx_model.json`). Once the run has enough previous live samples for the adapter's history window, the stored `PipelineCycle.arx_predicted` and `kf_x_prior` use that artifact prediction. If the artifact is missing or invalid, the request still succeeds with Kalman carry-forward prior; the internal warning is logged, not exposed as a filesystem path.

**Authentication**: Required — `Authorization: Token <token>`.
Provision a token once with:
```
python manage.py drf_create_token <username>
```

**Request body**

```json
{
  "run_id": 7,
  "timestamp": "2026-04-14T12:00:00Z",
  "soil_moisture": 45.3,
  "temperature": 22.1,
  "humidity": 65.0,
  "light": 120.0,
  "drip": 0.0,
  "mist": 0.0,
  "fan": 1.0
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | int | Yes | ID of a `live` ExperimentRun in `running` status whose greenhouse is active and owned by the authenticated user |
| `timestamp` | ISO-8601 UTC | Yes | Timestamp from the sensor |
| `soil_moisture` | float \| null | No | Primary Kalman channel (%) |
| `temperature` | float \| null | No | Stored for traceability |
| `humidity` | float \| null | No | Stored for traceability |
| `light` | float \| null | No | Stored for traceability |
| `drip` | float \| null | No | Actuator flag |
| `mist` | float \| null | No | Actuator flag |
| `fan` | float \| null | No | Actuator flag |

**Response `201 Created`**

```json
{
  "cycle_index": 0,
  "preprocess_status": "valid",
  "cycle_status": "ok",
  "adaptive_status": "R_updated",
  "kf_x_posterior": 45.1,
  "kf_innovation": 0.2
}
```

**Response `200 OK` (idempotent retry)**

The same `run_id` and `timestamp` may only produce one live `PipelineCycle` row. A duplicate POST with the **same sensor payload** (all optional channels match what was stored, including `null`) — e.g. client retry after timeout — returns `200` with the same body as the original cycle plus `"idempotent": true`. The Kalman step is **not** applied again.

If the same `timestamp` is sent again with **different** sensor values, the server responds with **`409 Conflict`** and does not overwrite the stored row.

```json
{
  "cycle_index": 0,
  "preprocess_status": "valid",
  "cycle_status": "ok",
  "adaptive_status": "R_updated",
  "kf_x_posterior": 45.1,
  "kf_innovation": 0.2,
  "idempotent": true
}
```

| Field | Type | Notes |
|-------|------|-------|
| `cycle_index` | int | Zero-based monotonic index within the run |
| `preprocess_status` | string | `valid` or `skipped` |
| `cycle_status` | string | `ok` / `skipped_no_measurement` / `error` |
| `adaptive_status` | string | `R_updated` / `R_skipped` / `skipped` |
| `kf_x_posterior` | float \| null | Filtered soil-moisture estimate |
| `kf_innovation` | float \| null | Measurement residual; null when no update |
| `idempotent` | bool | Present only on `200` duplicate-timestamp responses |

`arx_predicted` is intentionally not returned by this compact ingest response. It is persisted and visible through `GET /api/runs/{run_id}/series/`.

**Error responses**

| Status | Meaning |
|--------|---------|
| `400 Bad Request` | Payload validation failed (missing/invalid fields) |
| `401 Unauthorized` | Missing or invalid auth token |
| `403 Forbidden` | Authenticated user does not own the run's greenhouse, or the greenhouse is inactive |
| `404 Not Found` | `run_id` not found, or run is not of `live` type |
| `409 Conflict` | Run is not in `running` status (pending / completed / failed), **or** same `timestamp` already ingested with different sensor values (`code`: `duplicate_timestamp_payload_mismatch`) |

**Authorization**: Assign the `ExperimentRun` to a `Greenhouse`. The DRF token user must match `Greenhouse.owner`; `ExperimentRun` no longer stores a duplicated user owner.

**Reconnect / gap handling**: If the most recent persisted cycle has null Kalman fields (error recovery), the state resets from the `ExperimentConfig` defaults so the pipeline resumes cleanly.

---

## Dashboard Endpoints (Task #009)

### `GET /api/runs/`

List the 50 most-recent experiment runs, ordered newest first. In authenticated dashboard mode, the list is scoped to greenhouses owned by the current user.

**Query parameters**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `greenhouse_id` | int | *(omit)* | Optional filter. When authenticated, it still only returns runs for the current user's greenhouse. |

**Response** `200 OK`

```json
[
  {
    "id": 1,
    "name": "greenhouse-live-01",
    "run_type": "live",
    "status": "running",
    "greenhouse_id": 3,
    "greenhouse_name": "Greenhouse A",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Primary key |
| `name` | string | Human-readable label |
| `run_type` | string | `live` |
| `status` | string | `pending` / `running` / `completed` / `failed` |
| `greenhouse_id` | int | Greenhouse scope for this run |
| `greenhouse_name` | string | Human-readable greenhouse name |
| `created_at` | ISO-8601 datetime | |
| `dataset_source` | *(not returned)* | Omitted from this JSON to avoid exposing filesystem paths on open networks; the column remains in the database for provenance. |

---

### `GET /api/runs/{run_id}/series/`

Return `PipelineCycle` time-series rows for a single run.

**Query parameters**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `slice` | string | *(omit)* | If present, must be exactly `online`. Invalid values → `400`. Omit to include all rows. |
| `limit` | int | `2000` | Max rows returned (hard cap `10000`, minimum `1`) |
| `stride` | int | `1` | Return every Nth cycle (max `1000`). Product `limit × stride` must be ≤ **100 000** or the server returns `400` (DoS guard). |

**Response** `200 OK`

```json
{
  "run_id": 1,
  "run_name": "greenhouse-live-01",
  "greenhouse_id": 3,
  "greenhouse_name": "Greenhouse A",
  "run_status": "running",
  "total_cycles": 10000,
  "returned": 2000,
  "data": [
    {
      "greenhouse_id": 3,
      "cycle_index": 0,
      "slice_type": "online",
      "sample_ts": "2024-01-01T00:00:00Z",
      "raw_soil_moisture": 52.3,
      "arx_predicted": 52.5,
      "kf_x_posterior": 52.4,
      "kf_innovation": 0.2,
      "kf_R": 1.0,
      "latency_ms": 0.42,
      "preprocess_status": "valid",
      "cycle_status": "ok",
      "adaptive_status": "R_updated"
    }
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `greenhouse_id` | int | Greenhouse scope for the row |
| `cycle_index` | int | Zero-based monotonic index |
| `slice_type` | string | `online` |
| `sample_ts` | ISO-8601 \| null | Original sample timestamp |
| `raw_soil_moisture` | float \| null | Raw sensor reading |
| `arx_predicted` | float \| null | ARX model prediction |
| `kf_x_posterior` | float \| null | Adaptive Kalman posterior estimate |
| `kf_innovation` | float \| null | Measurement minus prediction |
| `kf_R` | float \| null | Current adaptive observation noise |
| `latency_ms` | float \| null | End-to-end cycle latency |
| `preprocess_status` | string | `valid` / `skipped` |
| `cycle_status` | string | `ok` / `skipped_no_measurement` / `error` |
| `adaptive_status` | string | `R_updated` / `R_skipped` / `skipped` |

**404** when `run_id` does not exist.

---

### `GET /api/runs/{run_id}/metrics/`

Return the online `EvaluationSummary` metrics for a run.

**Response** `200 OK`

```json
{
  "run_id": 1,
  "run_name": "greenhouse-live-01",
  "greenhouse_id": 3,
  "greenhouse_name": "Greenhouse A",
  "slices": {
    "online": {
      "slice_type": "online",
      "n_samples": 1000,
      "n_valid": 980,
      "n_skipped": 15,
      "n_error": 5,
      "rmse_arx": 0.42,
      "rmse_filtered": 0.38,
      "mae_arx": 0.35,
      "mae_filtered": 0.30,
      "variance_reduction": 0.25,
      "pass_variance_reduction": true,
      "pass_rmse_guardrail": true,
      "pass_mae_guardrail": true,
      "cycle_success_rate": 0.98,
      "sample_loss_rate": 0.02,
      "passes_acceptance_gate": true
    }
  }
}
```

**404** when `run_id` does not exist.

---

## AMPC Online Control Endpoints (Task #015)

These endpoints run the production AMPC path from persisted Kalman state. They never accept `artifact`, `state-json`, `input`, `output`, or model-path parameters from the request.

Authentication: required. Use DRF token auth (`Authorization: Token <token>`) or an authenticated Django session. Session-authenticated browser POST/PATCH requests must include Django CSRF protection, for example `X-CSRFToken`. Object authorization always checks `Greenhouse.owner`.

### `POST /api/greenhouses/{greenhouse_id}/ampc/recommendations/`

Run AMPC for one owned greenhouse and persist an audit row.

Request body must be empty:

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
    "bias_window_count": 12,
    "used_today_pump_seconds": 120.0,
    "actuator": {
      "enabled": false,
      "executed": false,
      "status": "disabled",
      "command": null,
      "http_status_code": null,
      "alert": null,
      "error": null
    },
    "created_at": "2026-05-09T10:00:00Z"
  },
  "error": null
}
```

Fail-closed responses for missing state, stale/future samples, insufficient history, model errors, solver errors, actuator config errors, and actuator HTTP failures are still persisted and returned with `pump_seconds: 0.0`, a non-`safe` `safety_status`, and a clear `reason`. Unsafe recommendations do not send actuator commands; their actuator status is `not_called`.

| Status | Meaning |
|--------|---------|
| `201 Created` | Recommendation/audit row persisted, including fail-closed outcomes |
| `400 Bad Request` | Body is not empty |
| `401 Unauthorized` | Missing/invalid authentication |
| `403 Forbidden` | Owned greenhouse is inactive |
| `404 Not Found` | Greenhouse missing or belongs to another user |

### `GET /api/greenhouses/{greenhouse_id}/ampc/recommendations/latest/`

Return the latest AMPC recommendation for an owned greenhouse.

| Status | Meaning |
|--------|---------|
| `200 OK` | Latest recommendation returned in the same envelope as POST |
| `401 Unauthorized` | Missing/invalid authentication |
| `404 Not Found` | Greenhouse missing/cross-user, or no recommendation exists |

### `GET /api/greenhouses/{greenhouse_id}/control-profile/`

Return the greenhouse controller profile, creating a default profile if it does not exist.

The response exposes user-facing settings and whether actuator config is present. It does not expose `actuator_url`, the token env var name, raw token values, or `settings.ARX_MODEL_PATH`.

### `PATCH /api/greenhouses/{greenhouse_id}/control-profile/`

Update whitelisted user-facing profile fields only:

| Field | Notes |
|-------|-------|
| `crop_name` | Human-readable crop/profile label |
| `crop_kc` | Positive crop coefficient placeholder for later ET/Dr work |
| `target_low`, `target_high` | Must satisfy `0 <= low < high <= 100` |
| `pump_max_seconds` | Positive per-step pump limit |
| `soft_daily_pump_cap_seconds` | Positive soft daily cap |
| `actuator_enabled` | Enables actuator branch only if operator-controlled URL/env config already exists |

System weights, actuator URL, actuator token env name, and model paths are not writable through this serializer.

Error envelope for AMPC/control-profile endpoints:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "invalid_profile",
    "message": "Control profile validation failed.",
    "details": {},
    "trace_id": "abc123..."
  }
}
```

---

## Core Data Contracts

### Input Sample

Expected fields, based on repo-root `ARX/greenhouse_data.csv`:

| Field | Required | Notes |
|-------|----------|-------|
| `Timestamp` | Yes | Measurement timestamp |
| `Soil_Moisture` | TBD | Candidate first estimation variable |
| `Temperature` | TBD | Candidate estimation or context variable |
| `Humidity` | TBD | Candidate estimation or context variable |
| `Light` | TBD | Candidate context variable |
| `Drip` | No | Actuator/status field from dataset |
| `Mist` | No | Actuator/status field from dataset |
| `Fan` | No | Actuator/status field from dataset |

### Preprocessing Result

| Field | Required | Notes |
|-------|----------|-------|
| `sample` | Yes | Validated sample payload |
| `status` | Yes | `valid` or `skipped` |
| `issues` | Yes | Validation or data-quality issues |

### Prediction Result

| Field | Required | Notes |
|-------|----------|-------|
| `value` | Yes | Next-step predicted `Soil_Moisture`; `null` when unavailable |
| `status` | Yes | `ok` / `unavailable` / `error` |
| `model_kind` | Yes | `arx`; future-compatible with LightGBM/XGBoost |
| `reason` | Yes | Explanation when `status` is not `ok`; empty string on success |

### Adaptive Kalman-ready Estimator Result

| Field | Required | Notes |
|-------|----------|-------|
| `filtered_state` | Yes | Filtered estimate (`kf_x_posterior`) |
| `residual` | Yes | Innovation: measurement minus prediction |
| `covariance` | Yes | `kf_P_posterior` |
| `adaptive_status` | Yes | `R_updated` / `R_skipped` / `skipped` |
| `status` | Yes | `ok` / `skipped_no_measurement` / `error` |

### AMPC Modeling Contract

| Field | Required | Notes |
|-------|----------|-------|
| `state_candidate` | TBD | `theta` soil moisture or `Dr` root-zone depletion |
| `control_inputs` | TBD | Drip/pump seconds, mist seconds, fan duration or level |
| `disturbances` | TBD | ET0/ETc, temperature, humidity, light |
| `cost_terms` | TBD | Zone/range tracking, water/energy penalty, actuator switching |
| `safety_constraints` | TBD | Bounds, daily water cap, RH max, no-mist rules, fallback rules |

The finalized production HTTP surface for the current single-pump AMPC path is documented in "AMPC Online Control Endpoints" above.

---

## Standard Error Shape

```json
{
  "detail": "Not found."
}
```

DRF returns standard 404/500 responses using the `detail` key.

---

## Future Endpoints

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| `GET` | `/api/runs/{id}` | Get run metadata and status | Deferred |
