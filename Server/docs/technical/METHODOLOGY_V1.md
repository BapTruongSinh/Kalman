<!--
DOCUMENT METADATA
Owner: @documentation-writer
Update trigger: Estimation methodology, metrics definitions, or AMPC boundary changes
Read by: Anyone defending v1 academically or extending toward AMPC
-->

# v1 Methodology — Adaptive Kalman Path and AMPC Boundary

> Last updated: 2026-05-08
> Version: 1.1.0
> Task reference: #012

This note complements [`ARCHITECTURE.md`](./ARCHITECTURE.md) (components and data flow) and [`DECISIONS.md`](./DECISIONS.md) (ADRs). It states the **scientific story** v1 is meant to support: live/online ingestion as the primary runtime, a pretrained ARX artifact as the explicit one-step predictor, scalar Adaptive Kalman-style filtering with **adaptive measurement noise `R`**, and traceable evaluation — while **AMPC** remains a documented control contract, not an executed closed-loop optimizer in v1.

---

## 1. Data and reproducibility

- **Primary live path**: samples POSTed to `/api/ingest/samples/` append `PipelineCycle` rows for a `live` run; methodology is the same per-step estimator, with different provenance and idempotency rules (see [`API.md`](./API.md)). The live runtime loads the server-side ARX artifact from `settings.ARX_MODEL_PATH` (default repo-root `ARX/arx_model.json`) and reconstructs the minimal history window from prior live cycles.
- **Dataset fixture**: `ARX/greenhouse_data.csv` remains available for external research/artifact generation, but the application no longer exposes replay/split/train orchestration.

---

## 2. Prediction layer (ARX baseline)

- **Role**: supply a **one-step-ahead** candidate for soil moisture before the Kalman measurement update, implementing the runtime `PredictionAdapter` contract (`predict()` + `load_artifact()`).
- **Model source**: the application runtime uses the pretrained `arx_model.json` artifact. OLS training and artifact creation belong outside the Django app.
- **Model**: ARX(*nₐ*, *nᵦ*, *nₖ*) in **OLS** form on lagged outputs and inputs; runtime reads the orders and input columns from the artifact metadata.
- **Outputs** (`PredictionResult`): predicted scalar in **`PredictionResult.value`** (`None` when unavailable), `status` (`ok` / `unavailable` / `error` — **never raises**), `model_kind` (`arx`), and `reason` when not `ok`.
- **Traceability in storage**: each `PipelineCycle` stores `arx_predicted` alongside raw and filtered channels.

---

## 3. Adaptive Kalman-ready update (v1 scope)

- **State**: scalar **soil moisture** estimate (aligned with ARX output variable).
- **Cycle**: time update with fixed **process noise `Q`**, then measurement update with **adaptive `R`** using innovation-squared tracking and EMA smoothing (`alpha`), clipped to `[R_min, R_max]` (see `KalmanConfig` / `CycleResult` in [`ARCHITECTURE.md`](./ARCHITECTURE.md) § Adaptive Kalman Cycle).
- **Innovation (residual for the measurement channel)**: \(e_k = z_k - x_{\text{prior},k}\) where \(z_k\) is the preprocessed measurement and \(x_{\text{prior},k}\) incorporates the ARX prior when available. Stored as `kf_innovation` on `PipelineCycle`.
- **Posterior**: `kf_x_posterior`, `kf_P_posterior`; gain `kf_K`; prior pair `kf_x_prior`, `kf_P_prior` when populated.
- **Adaptive status** (`adaptive_status`): `R_updated` when a measurement branch ran and `R` was considered for update; `R_skipped` when there was no usable measurement; `skipped` on internal error-handling paths. Distinct from **`cycle_status`** (`ok`, `skipped_no_measurement`, `error`).
- **Robustness**: validation / preprocessing attach explicit statuses per sample; estimator `step()` does not raise — failures become `cycle_status="error"` with `error_message` (task #011 tests).

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
| **Cost** | Zone tracking, water/energy, smoothing penalties | **Contracts only** — see [`ADAPTIVE_KALMAN_AMPC_NOTES.md`](./ADAPTIVE_KALMAN_AMPC_NOTES.md) and the quantitative handoff [`AMPC_MODELING_HANDOFF.md`](./AMPC_MODELING_HANDOFF.md) |
| **Safety** | RH caps, moisture bounds, mist/night rules, sensor-fault fallback | **Contracts + estimator robustness**; no enforced plant-wide safety solver |

For synthesis of research notes vs frozen decisions, cross-read [`DECISIONS.md`](./DECISIONS.md), [`ADAPTIVE_KALMAN_AMPC_NOTES.md`](./ADAPTIVE_KALMAN_AMPC_NOTES.md), and [`AMPC_MODELING_HANDOFF.md`](./AMPC_MODELING_HANDOFF.md).

---

## 6. Out of scope (later phases) — explicit list

The following are **intentionally excluded from v1 deliverables** but remain **in-project roadmap** wording:

| Deferred item | Why (v1) |
|----------------|----------|
| Full AMPC / HMPC **optimiser loop** and closed-loop actuator commands | Requires validated state + cost + constraint implementation beyond estimation demo |
| **Automatic online** model retraining and model registry | v1 live runtime uses the declared pretrained ARX artifact; artifact generation is outside the Django app |
| Multi-greenhouse multi-tenant SaaS scale | Single-run laboratory / demo scope |
| Native mobile apps | Web dashboard only |
| External weather / ET₀ physical model integration | Dataset-limited v1; fields may be added later |

**Not** deferred as “out of project”: **Adaptive Kalman estimation**, **AMPC-oriented documentation**, and **evaluation against `greenhouse_data.csv`**.

---

## 7. Further reading

| Document | Use when |
|----------|----------|
| [`USER_GUIDE.md`](../user/USER_GUIDE.md) | Run servers, dashboard, live ingest workflow |
| [`API.md`](./API.md) | REST shapes for runs, series, metrics, live ingest |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Module boundaries, `CycleResult` mapping, evaluation pipeline |
| [`DATABASE.md`](./DATABASE.md) | ORM tables and evaluation column semantics |
| [`AMPC_MODELING_HANDOFF.md`](./AMPC_MODELING_HANDOFF.md) | AMPC state / control / cost / safety synthesis (task #013) |
