<!--
DOCUMENT METADATA
Owner: @backend-developer
Update trigger: Any API endpoint or pipeline contract is added, modified, or removed
Read by: @frontend-developer and @qa-engineer
-->

# API Reference

> **Base URL (dev)**: `http://127.0.0.1:8000/api`
> **Authentication**: Dashboard endpoints are public (local dev). The live ingestion endpoint at `/api/ingest/samples/` requires a **DRF Token** (`Authorization: Token <token>`).
> **Content-Type**: `application/json`
> **Last updated**: 2026-04-15

**Pipeline semantics** (ARX vs Kalman roles, innovation/residual meaning, adaptive `R`, evaluation gates, AMPC contracts): see [`METHODOLOGY_V1.md`](./METHODOLOGY_V1.md). This file focuses on **HTTP shapes** and field lists.

---

## Live Ingestion Endpoint (Task #010)

### `POST /api/ingest/samples/`

Accept one live sensor reading from a device and run a single Adaptive Kalman step.

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
| `run_id` | int | Yes | ID of a `live` ExperimentRun in `running` status with a non-null `owner` matching the authenticated user |
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

**Error responses**

| Status | Meaning |
|--------|---------|
| `400 Bad Request` | Payload validation failed (missing/invalid fields) |
| `401 Unauthorized` | Missing or invalid auth token |
| `403 Forbidden` | Authenticated user is not the run `owner`, or the run has no `owner` set |
| `404 Not Found` | `run_id` not found, or run is not of `live` type |
| `409 Conflict` | Run is not in `running` status (pending / completed / failed), **or** same `timestamp` already ingested with different sensor values (`code`: `duplicate_timestamp_payload_mismatch`) |

**Authorization**: Assign `ExperimentRun.owner` to the device user (same account as the DRF token). Only that user may POST samples for the run.

**Reconnect / gap handling**: If the most recent persisted cycle has null Kalman fields (error recovery), the state resets from the `ExperimentConfig` defaults so the pipeline resumes cleanly.

---

## Dashboard Endpoints (Task #009)

### `GET /api/runs/`

List the 50 most-recent experiment runs, ordered newest first.

**Response** `200 OK`

```json
[
  {
    "id": 1,
    "name": "replay-2024-01",
    "run_type": "offline_replay",
    "status": "completed",
    "created_at": "2024-01-01T00:00:00Z",
    "dataset_source": null
  }
]
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Primary key |
| `name` | string | Human-readable label |
| `run_type` | string | `offline_replay` or `live` |
| `status` | string | `pending` / `running` / `completed` / `failed` |
| `created_at` | ISO-8601 datetime | |
| `dataset_source` | string \| null | Path / URL of source dataset |

---

### `GET /api/runs/{run_id}/series/`

Return `PipelineCycle` time-series rows for a single run.

**Query parameters**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `slice` | string | *(all)* | Filter to `train`, `validation`, or `test` |
| `limit` | int | `2000` | Max rows returned (hard cap `10000`) |
| `stride` | int | `1` | Return every Nth cycle (for downsampling) |

**Response** `200 OK`

```json
{
  "run_id": 1,
  "run_name": "replay-2024-01",
  "run_status": "completed",
  "total_cycles": 10000,
  "returned": 2000,
  "data": [
    {
      "cycle_index": 0,
      "slice_type": "train",
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
| `cycle_index` | int | Zero-based monotonic index |
| `slice_type` | string | `train` / `validation` / `test` |
| `sample_ts` | ISO-8601 \| null | Original sample timestamp |
| `raw_soil_moisture` | float \| null | Raw sensor reading |
| `arx_predicted` | float \| null | ARX model prediction |
| `kf_x_posterior` | float \| null | Adaptive Kalman posterior estimate |
| `kf_innovation` | float \| null | Measurement minus prediction |
| `kf_R` | float \| null | Current adaptive observation noise |
| `latency_ms` | float \| null | End-to-end cycle latency |
| `preprocess_status` | string | `valid` / `kept_last` / `interpolated` / `skipped` / `invalid` |
| `cycle_status` | string | `ok` / `error` / `skipped_invalid` |
| `adaptive_status` | string | `R_updated` / `R_skipped` / `skipped` |

**404** when `run_id` does not exist.

---

### `GET /api/runs/{run_id}/metrics/`

Return `EvaluationSummary` metrics for each data slice of a run.

**Response** `200 OK`

```json
{
  "run_id": 1,
  "run_name": "replay-2024-01",
  "slices": {
    "test": {
      "slice_type": "test",
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
| `status` | Yes | `valid`, `kept_last`, `interpolated`, `skipped`, or `invalid` |
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
| `status` | Yes | `ok` / `error` / `skipped_invalid` |

### AMPC Contract Placeholder

This is a modeling contract for later controller work, not a finalized HTTP endpoint.

| Field | Required | Notes |
|-------|----------|-------|
| `state_candidate` | TBD | `theta` soil moisture or `Dr` root-zone depletion |
| `control_inputs` | TBD | Drip/pump seconds, mist seconds, fan duration or level |
| `disturbances` | TBD | ET0/ETc, temperature, humidity, light |
| `cost_terms` | TBD | Zone/range tracking, water/energy penalty, actuator switching |
| `safety_constraints` | TBD | Bounds, daily water cap, RH max, no-mist rules, fallback rules |

---

## Standard Error Shape

```json
{
  "detail": "Not found."
}
```

DRF returns standard 404/500 responses using the `detail` key.

---

## Planned Endpoints

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| `POST` | `/api/runs/replay` | Start replay from repo-root `ARX/greenhouse_data.csv` | TBD |
| `GET` | `/api/runs/{id}` | Get run metadata and status | TBD |
| `POST` | `/api/samples` | Submit a live sensor sample | TBD |
