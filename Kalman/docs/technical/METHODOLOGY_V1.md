<!--
DOCUMENT METADATA
Owner: @documentation-writer
Update trigger: Estimation methodology, metrics definitions, or AMPC boundary changes
Read by: Anyone defending v1 academically or extending toward AMPC
-->

# v1 Methodology — Adaptive Kalman Path and AMPC Boundary

> Last updated: 2026-04-15
> Version: 1.0.0
> Task reference: #012

This note complements [`ARCHITECTURE.md`](./ARCHITECTURE.md) (components and data flow) and [`DECISIONS.md`](./DECISIONS.md) (ADRs). It states the **scientific story** v1 is meant to support: reproducible offline replay on greenhouse time series, ARX as an explicit baseline predictor, scalar Adaptive Kalman-style filtering with **adaptive measurement noise `R`**, and traceable evaluation — while **AMPC** remains a documented control contract, not an executed closed-loop optimizer in v1.

---

## 1. Data and reproducibility

- **Primary offline dataset**: at repo root, `ARX/greenhouse_data.csv` (timestamped soil moisture, environment, and actuator fields). From `Kalman/backend/`, that file is `../../ARX/greenhouse_data.csv`. Same file + same persisted `RunConfig` (stored in `ExperimentConfig.raw_config_json`) must yield the same pipeline parameters; cycle-level outputs depend only on ingested rows and config.
- **Ingestion**: `load_csv` normalises types, attaches **UTC** to parsed timestamps (naive CSV strings are interpreted as UTC for ORM compatibility), skips unparseable timestamps, and preserves row order after a defensive chronological sort before splitting.
- **Chronological split**: default **60% / 20% / 20%** (`train` / `validation` / `test`) via `split_chronological`. ARX is trained on the **train** slice (and may report optional metrics on **validation**). Final acceptance metrics are interpreted on the **test** slice (ADR-003 gate); see evaluation section below.
- **Live path** (optional): samples POSTed to `/api/ingest/samples/` append `PipelineCycle` rows for a `live` run; methodology is the same per-step estimator, with different provenance and idempotency rules (see [`API.md`](./API.md)).

---

## 2. Prediction layer (ARX baseline)

- **Role**: supply a **one-step-ahead** candidate for soil moisture before the Kalman measurement update, implementing `PredictionAdapter`.
- **Model**: ARX(*nₐ*, *nᵦ*, *nₖ*) in **OLS** form on lagged outputs and inputs; defaults align with `RunConfig` / `ARXTrainConfig` (*nₐ* = 2, *nᵦ* = 2, *nₖ* = 1).
- **Outputs** (`PredictionResult`): predicted scalar in **`PredictionResult.value`** (`None` when unavailable), `status` (`ok` / `unavailable` / `error` — **never raises**), `model_kind` (`arx`), and `reason` when not `ok`.
- **Traceability in storage**: each `PipelineCycle` stores `arx_predicted` alongside raw and filtered channels.

---

## 3. Adaptive Kalman-ready update (v1 scope)

- **State**: scalar **soil moisture** estimate (aligned with ARX output variable).
- **Cycle**: time update with fixed **process noise `Q`**, then measurement update with **adaptive `R`** using innovation-squared tracking and EMA smoothing (`alpha`), clipped to `[R_min, R_max]` (see `KalmanConfig` / `CycleResult` in [`ARCHITECTURE.md`](./ARCHITECTURE.md) § Adaptive Kalman Cycle).
- **Innovation (residual for the measurement channel)**: \(e_k = z_k - x_{\text{prior},k}\) where \(z_k\) is the preprocessed measurement and \(x_{\text{prior},k}\) incorporates the ARX prior when available. Stored as `kf_innovation` on `PipelineCycle`.
- **Posterior**: `kf_x_posterior`, `kf_P_posterior`; gain `kf_K`; prior pair `kf_x_prior`, `kf_P_prior` when populated.
- **Adaptive status** (`adaptive_status`): `R_updated` when a measurement branch ran and `R` was considered for update; `R_skipped` when there was no usable measurement; `skipped` on internal error-handling paths. Distinct from **`cycle_status`** (`ok`, `skipped_no_measurement`, `skipped_invalid`, `error`).
- **Robustness**: validation / preprocessing attach explicit statuses per sample; the estimator **`step` / `replay` does not raise** — failures become `cycle_status="error"` with `error_message` (task #011 tests).

---

## 4. Evaluation outputs (what “proves improvement”)

Computed from persisted cycles (per slice) by `estimation.evaluation`:

| Output | Meaning |
|--------|---------|
| `SliceMetrics` / `EvaluationSummary` | RMSE/MAE for raw vs ARX vs filtered, innovation summaries, latency stats, counts of ok / skipped / error cycles |
| **Variance reduction** | First-difference variance: raw vs filtered — ADR-003 primary gate |
| **Guardrails** | Filtered RMSE/MAE not worse than ARX by more than an agreed margin (see ADR-003 flags on summary rows) |
| **`passes_acceptance_gate`** | Combined boolean on the **test** slice for demo sign-off |
| **Text / CSV / plots** | `build_text_report(run_id)`, `export_to_csv(...)`, `export_plots(...)` (plots require compatible `matplotlib` / NumPy ABI) |

Detailed field lists: [`DATABASE.md`](./DATABASE.md) (`evaluation_summaries`), implementation notes in [`ARCHITECTURE.md`](./ARCHITECTURE.md) § Evaluation.

---

## 5. AMPC-ready contracts (documentation-only in v1)

v1 **does** include Adaptive Kalman estimation as the on-ramp to later **AMPC** (Adaptive / economic MPC style greenhouse control). What is deferred is **closed-loop optimisation and autonomous actuation**, not the research topic.

| Contract | v1 meaning (documentation) | Implementation status |
|----------|----------------------------|-------------------------|
| **State** | Scalar soil moisture estimate \(\theta\); AMPC-oriented **root-zone depletion `Dr`** documented as a future derived state | `Dr` not estimated in v1 code |
| **Control** | Drip / mist / fan actuators as eventual decision variables | Actuator columns ingested for traceability; **no MPC solver** |
| **Disturbances** | Temperature, humidity, light (and related fields) as exogenous inputs | Used in ARX / stored on cycles |
| **Cost** | Zone tracking, water/energy, smoothing penalties | **Contracts only** — see [`ADAPTIVE_KALMAN_AMPC_NOTES.md`](./ADAPTIVE_KALMAN_AMPC_NOTES.md) |
| **Safety** | RH caps, moisture bounds, mist/night rules, sensor-fault fallback | **Contracts + estimator robustness**; no enforced plant-wide safety solver |

For synthesis of research notes vs frozen decisions, cross-read [`DECISIONS.md`](./DECISIONS.md) and [`ADAPTIVE_KALMAN_AMPC_NOTES.md`](./ADAPTIVE_KALMAN_AMPC_NOTES.md).

---

## 6. Out of scope (later phases) — explicit list

The following are **intentionally excluded from v1 deliverables** but remain **in-project roadmap** wording:

| Deferred item | Why (v1) |
|----------------|----------|
| Full AMPC / HMPC **optimiser loop** and closed-loop actuator commands | Requires validated state + cost + constraint implementation beyond estimation demo |
| **Automatic online** model retraining and model registry | v1 uses **offline** ARX retrain on declared slices; registry is manual / file-based |
| Multi-greenhouse multi-tenant SaaS scale | Single-run laboratory / demo scope |
| Native mobile apps | Web dashboard only |
| External weather / ET₀ physical model integration | Dataset-limited v1; fields may be added later |

**Not** deferred as “out of project”: **Adaptive Kalman estimation**, **AMPC-oriented documentation**, and **evaluation against `greenhouse_data.csv`**.

---

## 7. Further reading

| Document | Use when |
|----------|----------|
| [`USER_GUIDE.md`](../user/USER_GUIDE.md) | Run servers, dashboard, shell replay recipe |
| [`API.md`](./API.md) | REST shapes for runs, series, metrics, live ingest |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Module boundaries, `CycleResult` mapping, evaluation pipeline |
| [`DATABASE.md`](./DATABASE.md) | ORM tables and evaluation column semantics |
