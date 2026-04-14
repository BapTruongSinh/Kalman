<!--
DOCUMENT METADATA
Owner: @database-expert
Update trigger: Any schema change, migration, index addition, or significant query pattern decision
Read by: @backend-developer and @systems-architect
-->

# Database Reference

> **Engine**: MySQL from XAMPP
> **ORM / Query layer**: Django ORM
> **Connection**: `DATABASE_URL` or Django database settings
> **Last updated**: 2026-04-14

---

## Schema Overview

The v1 schema is not implemented yet. It must support experiment reproducibility and traceability for the prediction plus Adaptive Kalman-ready pipeline, with enough metadata to feed later AMPC analysis.

Expected conceptual entities:

```text
experiment_runs
  |
  +-- experiment_configs
  |
  +-- raw_measurements
  |
  +-- prediction_outputs
  |
  +-- filtered_estimates
  |
  +-- adaptive_estimator_statuses
  |
  +-- pipeline_events
  |
  +-- evaluation_metrics
```

---

## Required Stored Data

| Data | Required | Notes |
|------|----------|-------|
| Raw measurement | Yes | Original input values from CSV or live sample |
| Timestamp | Yes | Source timestamp or ingestion timestamp |
| Variable identifier | Yes | Example: soil moisture, temperature, humidity, light |
| Preprocessing status | Yes | Valid, corrected, interpolated, skipped, or invalid |
| Prediction output | Yes | Prediction used by the estimator update; ARX is the initial baseline |
| Filtered estimate | Yes | Adaptive Kalman-ready filtered output |
| Residual / innovation | Yes | Diagnostic value for evaluation |
| Adaptive status | TBD | Parameter update status or rationale if adaptive behavior is enabled |
| AMPC handoff fields | TBD | Candidate state/control/disturbance identifiers when task #013 finalizes them |
| Pipeline status log | Yes | Step status, failures, skipped updates |
| Run configuration | Yes | Sampling time, initial state, covariance settings, adaptive bounds/rules, prediction model settings |

---

## Candidate Tables

These are planning placeholders and should be replaced by Django model details once task #002 is complete.

| Table | Purpose | Status |
|-------|---------|--------|
| `experiment_runs` | One row per replay or live test run | Planned |
| `experiment_configs` | Saved configuration snapshot for reproducibility | Planned |
| `raw_measurements` | Raw sensor or dataset rows | Planned |
| `prediction_outputs` | Prediction outputs per time step; ARX baseline first | Planned |
| `filtered_estimates` | Filtered state and residual/innovation data per time step | Planned |
| `adaptive_estimator_statuses` | Adaptive parameter status, rule names, and bounds when enabled | Planned |
| `pipeline_events` | Validation, preprocessing, and runtime status logs | Planned |
| `evaluation_metrics` | Variance reduction, residual behavior, MAE/RMSE, latency, sample loss, optional AMPC-readiness metrics | Planned |

---

## Open Decisions

- Whether official v1 storage is MySQL only or MySQL plus CSV export.
- Which variables are first-class estimated state variables.
- Whether the official first AMPC state is soil moisture `theta`, root-zone depletion `Dr`, or both.
- Whether covariance values are stored for every time step or only summary diagnostics.
- Whether adaptive status is stored inline with estimates or in a separate table.
- Whether live sensor samples and CSV replay samples share one table or use separate source-specific tables.
