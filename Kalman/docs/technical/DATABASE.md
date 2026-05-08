<!--
DOCUMENT METADATA
Owner: @database-expert
Update trigger: Any schema change, migration, index addition, or significant query pattern decision
Read by: @backend-developer and @systems-architect
-->

# Database Reference

> **Engine**: MySQL from XAMPP
> **ORM / Query layer**: Django ORM
> **Connection**: `DATABASE_URL` or Django `DATABASES` settings
> **Last updated**: 2026-05-08

---

## Storage Format Decision (from ADR-003 / task #001)

| Question | Decision |
|----------|----------|
| Official local source of truth | MySQL from XAMPP via Django ORM |
| CSV role | External research/artifact input only; not an application runtime input |
| Live sensor storage | Uses MySQL tables with live-only vocabulary |
| Export policy | Any run can be exported to CSV on demand |

Runtime update from ADR-004: application runtime creates/uses `run_type='live'` runs, persists `source_type='live'` cycles, and evaluates the single `slice_type='online'` stream. Migration `0006_live_only_cleanup` removes replay/train schema surface and normalizes old rows.

---

## Schema Overview

Four tables cover one live run, from configuration through per-cycle estimation to online evaluation metrics.

```text
experiment_runs  (1)
     |
     +--< experiment_configs     (1:1 per run, frozen snapshot)
     |
     +--< pipeline_cycles        (1:N per run, one row per time step)
     |
     +--< evaluation_summaries   (1:1 per run, online summary)
```

---

## Table: `experiment_runs`

One row per live estimation run. The single reference point for tracing all outputs.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | INT AUTO_INCREMENT | No | — | Primary key |
| `name` | VARCHAR(255) | No | — | Human-readable run label |
| `run_type` | VARCHAR(20) | No | `'live'` | Django choices: `live` |
| `status` | VARCHAR(20) | No | `'pending'` | Django choices: `pending`, `running`, `completed`, `failed`, `aborted` |
| `dataset_source` | VARCHAR(512) | Yes | NULL | Live source, device, or deployment description for this run |
| `created_at` | DATETIME | No | `NOW()` | Row creation time |
| `started_at` | DATETIME | Yes | NULL | Set when run begins |
| `completed_at` | DATETIME | Yes | NULL | Set when run ends |
| `notes` | TEXT | Yes | NULL | Free-form comments |

**Indexes**: PRIMARY KEY (`id`), INDEX `idx_runs_status` (`status`), INDEX `idx_runs_created` (`created_at`)

> `run_type` and `status` are `VARCHAR` validated via Django choices, not MySQL `ENUM`.

---

## Table: `experiment_configs`

Frozen configuration snapshot created at run start.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | INT AUTO_INCREMENT | No | — | Primary key |
| `run_id` | INT | No | — | FK → `experiment_runs.id` |
| `x0` | FLOAT | No | 0.0 | Initial Kalman state estimate (first observed `Soil_Moisture`) |
| `P0` | FLOAT | No | 1.0 | Initial state covariance |
| `Q` | FLOAT | No | 0.05 | Process noise; selected by validation tuning, default 0.05 |
| `R0` | FLOAT | No | 1.0 | Initial measurement noise (adaptive `R` starts here) |
| `R_min` | FLOAT | No | 0.05 | Lower bound for adaptive `R` |
| `R_max` | FLOAT | No | 25.0 | Upper bound for adaptive `R` |
| `alpha` | FLOAT | No | 0.95 | EMA smoothing factor for adaptive `R` update |
| `raw_config_json` | TEXT | No | `'{}'` | Full serialized config as JSON for complete reproducibility |
| `created_at` | DATETIME | No | `NOW()` | — |

**Indexes**: PRIMARY KEY (`id`), UNIQUE KEY `uq_config_run` (`run_id`)

---

## Table: `pipeline_cycles`

One row per processed time step within a run. The core data table. Every filtered value is traceable back to its raw measurement, ARX prediction, Kalman internals, adaptive status, and configuration via `run_id`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | BIGINT AUTO_INCREMENT | No | — | Primary key |
| `run_id` | INT | No | — | FK → `experiment_runs.id` |
| `sample_ts` | DATETIME | No | — | Source timestamp from dataset; Django `DateTimeField` maps to DATETIME without explicit sub-second precision |
| `cycle_index` | INT | No | — | Sequential 0-based index within the run |
| `ingest_dedupe_key` | VARCHAR(191) | No | — | Stable idempotency string per run (`live|{run_id}|{UTC timestamp}`) |
| `slice_type` | VARCHAR(15) | No | `'online'` | Django choices: `online` |
| `source_type` | VARCHAR(20) | No | `'live'` | Django choices: `live` |
| **Raw measurements** | | | | |
| `raw_soil_moisture` | FLOAT | Yes | NULL | Raw `Soil_Moisture` from source |
| `raw_temperature` | FLOAT | Yes | NULL | Raw `Temperature` |
| `raw_humidity` | FLOAT | Yes | NULL | Raw `Humidity` |
| `raw_light` | FLOAT | Yes | NULL | Raw `Light` |
| `raw_drip` | FLOAT | Yes | NULL | Raw `Drip` actuator signal |
| `raw_mist` | FLOAT | Yes | NULL | Raw `Mist` actuator signal |
| `raw_fan` | FLOAT | Yes | NULL | Raw `Fan` actuator signal |
| **Preprocessing** | | | | |
| `preprocess_status` | VARCHAR(20) | No | `'valid'` | Django choices: `valid`, `skipped` |
| **ARX prediction** | | | | |
| `arx_predicted` | FLOAT | Yes | NULL | ARX next-step prediction for `Soil_Moisture` from `settings.ARX_MODEL_PATH` on live runtime; NULL if prediction skipped/unavailable |
| **Kalman internals** | | | | |
| `kf_x_prior` | FLOAT | Yes | NULL | Prior estimate `x^-_k` before measurement update |
| `kf_P_prior` | FLOAT | Yes | NULL | Prior covariance `P^-_k` before measurement update |
| `kf_innovation` | FLOAT | Yes | NULL | Innovation `e_k = z_k - x^-_k` |
| `kf_R` | FLOAT | Yes | NULL | Adaptive `R_k` used at this step |
| `kf_K` | FLOAT | Yes | NULL | Kalman gain `K_k` |
| `kf_x_posterior` | FLOAT | Yes | NULL | Filtered estimate `x_k` after update |
| `kf_P_posterior` | FLOAT | Yes | NULL | Updated covariance `P_k` after update |
| **Cycle status** | | | | |
| `cycle_status` | VARCHAR(30) | No | `'ok'` | Django choices: `ok`, `skipped_no_measurement`, `error` |
| `error_message` | VARCHAR(512) | Yes | NULL | Short error description if `cycle_status = 'error'` |
| `created_at` | DATETIME | No | `NOW()` | Row insertion time |

**Constraints / Indexes**:
- PRIMARY KEY (`id`)
- UNIQUE `uq_cycles_run_index` (`run_id`, `cycle_index`) — one cycle per index per run
- UNIQUE `uq_cycles_run_ingest_dedupe` (`run_id`, `ingest_dedupe_key`) — at most one row per run per live timestamp key
- INDEX `idx_cycles_run_ts` (`run_id`, `sample_ts`) — time-series retrieval per run
- INDEX `idx_cycles_run_slice` (`run_id`, `slice_type`) — slice-level queries and metrics

> **Note on column types**: `slice_type`, `source_type`, `preprocess_status`, and `cycle_status` are stored as `VARCHAR` with Django-level choice validation, not native MySQL `ENUM`. This keeps migrations simple and avoids MySQL ENUM migration pain. Choice values are enforced at the ORM layer.

---

## Table: `evaluation_summaries`

Aggregated metrics per live run. The single `online` row is the evaluation summary.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | INT AUTO_INCREMENT | No | — | Primary key |
| `run_id` | INT | No | — | FK → `experiment_runs.id` |
| `slice_type` | VARCHAR(15) | No | `'online'` | Django choices: `online` |
| `n_samples` | INT | No | — | Total time steps in slice |
| `n_valid` | INT | No | — | Cycles with `cycle_status = 'ok'` |
| `n_skipped` | INT | No | — | Cycles where measurement update was skipped |
| `n_error` | INT | No | — | Cycles with `cycle_status = 'error'` |
| **ARX accuracy** | | | | |
| `rmse_arx` | FLOAT | Yes | NULL | RMSE of `arx_predicted` vs `raw_soil_moisture` |
| `mae_arx` | FLOAT | Yes | NULL | MAE of `arx_predicted` vs `raw_soil_moisture` |
| **Kalman accuracy** | | | | |
| `rmse_filtered` | FLOAT | Yes | NULL | RMSE of `kf_x_posterior` vs `raw_soil_moisture` |
| `mae_filtered` | FLOAT | Yes | NULL | MAE of `kf_x_posterior` vs `raw_soil_moisture` |
| **Good-enough metrics (ADR-003)** | | | | |
| `var_diff_raw` | FLOAT | Yes | NULL | `var(diff(raw_soil_moisture))` — variance of raw first differences |
| `var_diff_filtered` | FLOAT | Yes | NULL | `var(diff(kf_x_posterior))` — variance of filtered first differences |
| `variance_reduction` | FLOAT | Yes | NULL | `1 - var_diff_filtered / var_diff_raw` |
| `rmse_ratio` | FLOAT | Yes | NULL | `rmse_filtered / rmse_arx` |
| `mae_ratio` | FLOAT | Yes | NULL | `mae_filtered / mae_arx` |
| **Innovation and adaptive R diagnostics** | | | | |
| `innovation_mean` | FLOAT | Yes | NULL | Mean of `kf_innovation` |
| `innovation_std` | FLOAT | Yes | NULL | Std dev of `kf_innovation` |
| `innovation_max_abs` | FLOAT | Yes | NULL | Max absolute innovation (saturation check) |
| `R_mean` | FLOAT | Yes | NULL | Mean adaptive `R` over slice |
| `R_min_observed` | FLOAT | Yes | NULL | Min observed `R` |
| `R_max_observed` | FLOAT | Yes | NULL | Max observed `R` |
| `P_mean` | FLOAT | Yes | NULL | Mean posterior covariance `P` |
| `P_max` | FLOAT | Yes | NULL | Max posterior covariance (explosion check) |
| **Pass/fail flags** | | | | |
| `pass_variance_reduction` | TINYINT(1) | Yes | NULL | 1 if `variance_reduction >= 0.20` |
| `pass_rmse_guardrail` | TINYINT(1) | Yes | NULL | 1 if `rmse_ratio <= 1.05` |
| `pass_mae_guardrail` | TINYINT(1) | Yes | NULL | 1 if `mae_ratio <= 1.05` |
| `created_at` | DATETIME | No | `NOW()` | — |

**Indexes**:
- PRIMARY KEY (`id`)
- UNIQUE KEY `uq_eval_run_slice` (`run_id`, `slice_type`)

---

## Relationships Summary

```text
experiment_runs.id  <──  experiment_configs.run_id   (1:1)
experiment_runs.id  <──  arx_artifacts.run_id         (1:1)
experiment_runs.id  <──  pipeline_cycles.run_id        (1:N)
experiment_runs.id  <──  evaluation_summaries.run_id   (1:3 max)
```

All foreign keys use `ON DELETE CASCADE` so deleting a run removes all its associated data.

---

## Query Patterns

### Replay all cycles for a run in order

```sql
SELECT cycle_index, sample_ts,
       raw_soil_moisture, arx_predicted,
       kf_x_posterior, kf_innovation, kf_R, kf_P_posterior,
       preprocess_status, cycle_status
FROM pipeline_cycles
WHERE run_id = %s
ORDER BY cycle_index ASC;
```

### Get test-slice cycles for dashboard/plot

```sql
SELECT sample_ts,
       raw_soil_moisture, arx_predicted, kf_x_posterior,
       kf_innovation, kf_R, kf_P_posterior,
       preprocess_status, cycle_status
FROM pipeline_cycles
WHERE run_id = %s AND slice_type = 'online'
ORDER BY sample_ts ASC;
```

### Check acceptance gate for the online stream

```sql
SELECT variance_reduction, rmse_ratio, mae_ratio,
       pass_variance_reduction, pass_rmse_guardrail, pass_mae_guardrail
FROM evaluation_summaries
WHERE run_id = %s AND slice_type = 'online';
```

### List all completed runs with their online metrics

```sql
SELECT r.id, r.name, r.completed_at,
       e.variance_reduction, e.rmse_ratio, e.mae_ratio,
       e.pass_variance_reduction, e.pass_rmse_guardrail, e.pass_mae_guardrail
FROM experiment_runs r
LEFT JOIN evaluation_summaries e ON e.run_id = r.id AND e.slice_type = 'test'
WHERE r.status = 'completed'
ORDER BY r.completed_at DESC;
```

---

## Migration Notes

- All tables use `utf8mb4` charset.
- `pipeline_cycles.sample_ts` uses `DATETIME`; Django `DateTimeField` does not request explicit sub-second precision. If millisecond precision is required later, add a custom DDL migration.
- Django migrations live in `backend/estimation/migrations/`.
- First migration: `0001_initial.py` — creates all five tables.
- Do not use `CASCADE DELETE` in production before confirming that run data is exported/backed up.

---

## Open Items

| Item | Owner | Status |
|------|-------|--------|
| AMPC-ready derived columns (`Dr`, `ETc`, `ET0`) | task #013 | **Contract** documented in [`AMPC_MODELING_HANDOFF.md`](./AMPC_MODELING_HANDOFF.md); **schema** still deferred until a controller phase needs persisted ET/Dr series |
| Live sensor multi-source schema extension | task #010 | Deferred; `source_type` column is already present for forward compatibility |
| CSV export stored procedure or management command | task #008 | Planned as part of evaluation/report export |

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Codex | Initial placeholder schema overview created during onboarding |
| 2026-04-15 | Cursor | Open item AMPC columns: contract finalized in `AMPC_MODELING_HANDOFF.md` (task #013); schema migration unchanged deferred. |
| 2026-04-14 | Codex | Full schema designed for task #002: five tables, all columns, indexes, query patterns, storage decision, and open items |
| 2026-05-08 | Codex | Documented ADR-004 runtime shift: live cycles use server-side ARX artifact path; schema unchanged. |
