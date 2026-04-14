<!--
DOCUMENT METADATA
Owner: @backend-developer
Update trigger: Any API endpoint or pipeline contract is added, modified, or removed
Read by: @frontend-developer and @qa-engineer
-->

# API Reference

> **Base URL**: TBD
> **Authentication**: TBD; configuration-changing endpoints must be protected
> **Content-Type**: `application/json` for HTTP APIs
> **Last updated**: 2026-04-14

---

## Status

No production API endpoints are finalized yet. v1 still needs to decide whether the first implementation exposes HTTP endpoints, internal Python services, generated artifacts, or a combination of these.

The core contract that must be preserved is the Adaptive Kalman + AMPC-ready estimation pipeline contract:

```text
Input sample/history -> Preprocessing result -> Prediction result -> Adaptive Kalman-ready estimator result -> Stored run output -> Evaluation output
```

---

## Core Data Contracts

### Input Sample

Expected fields, based on `../ARX/greenhouse_data.csv`:

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
| `status` | Yes | `valid`, `kept_last`, `interpolated`, or `skipped` (preprocess_status) |
| `issues` | Yes | Validation or data-quality issues |

### Prediction Result

| Field | Required | Notes |
|-------|----------|-------|
| `prediction` | Yes | Next-step predicted state or output |
| `status` | Yes | Prediction status |
| `model_kind` | Yes | Example: `arx`; future-compatible with LightGBM/XGBoost if selected |
| `config_id` | Yes | Prediction configuration or model reference |

### Adaptive Kalman-ready Estimator Result

| Field | Required | Notes |
|-------|----------|-------|
| `filtered_state` | Yes | Filtered estimate |
| `residual` | Yes | Measurement minus prediction or innovation-equivalent value |
| `covariance` | TBD | Include if needed for diagnostics |
| `adaptive_status` | TBD | Include when task #001 selects adaptive `Q`/`R` or another adaptive rule |
| `status` | Yes | Update status |

### AMPC Contract Placeholder

This is a modeling contract for later controller work, not a finalized HTTP endpoint.

| Field | Required | Notes |
|-------|----------|-------|
| `state_candidate` | TBD | `theta` soil moisture or `Dr` root-zone depletion |
| `control_inputs` | TBD | Drip/pump seconds, mist seconds, fan duration or level |
| `disturbances` | TBD | ET0/ETc, temperature, humidity, light, depending on task #001/#013 |
| `cost_terms` | TBD | Zone/range tracking, water/energy penalty, actuator switching, `Delta u` smoothing |
| `safety_constraints` | TBD | Bounds, daily water cap, RH max, no-mist rules, fallback rules |

---

## Standard Error Shape

If HTTP APIs are added, use this shape:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The sample could not be processed.",
    "details": [],
    "trace_id": "TBD"
  }
}
```

---

## Planned Endpoints

Endpoint design is not final. Candidate v1 endpoints:

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| `POST` | `/api/runs/replay` | Start replay from `../ARX/greenhouse_data.csv` | TBD |
| `GET` | `/api/runs/{id}` | Get run metadata and status | TBD |
| `GET` | `/api/runs/{id}/series` | Get raw, predicted, and filtered series | TBD |
| `GET` | `/api/runs/{id}/metrics` | Get evaluation metrics | TBD |
| `POST` | `/api/samples` | Submit a live sensor sample | TBD |
