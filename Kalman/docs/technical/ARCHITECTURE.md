<!--
DOCUMENT METADATA
Owner: @systems-architect
Update trigger: System architecture changes, new integrations, component additions
Read by: All agents. Always read before making implementation decisions.
For design tokens, component specs, and UX flows see DESIGN_SYSTEM.md.
-->

# System Architecture

> Last updated: 2026-04-15
> Version: 0.2.0

---

## Overview

The v1 system is an offline-first greenhouse state-estimation pipeline oriented toward Adaptive Kalman plus AMPC. It accepts replay records loaded from a time-series table or from the current CSV snapshot at `../ARX/greenhouse_data.csv`, validates and preprocesses those records, chronologically splits them into train/validation/test slices, optionally retrains the ARX baseline offline for the selected run, asks a prediction adapter for a next-step prediction, uses the estimator module for an Adaptive Kalman-ready update with the real measurement, then stores and visualizes raw, predicted, and filtered values.

The core architectural decision is to keep v1 staged while preventing a wrong baseline-only design. The first estimator target is scalar `Soil_Moisture`, the minimal adaptive mechanism is bounded innovation-driven adaptive `R` with fixed-per-run `Q`, and full closed-loop AMPC actuation is postponed until the prediction plus Adaptive Kalman foundation is validated. AMPC state/control/disturbance/cost/safety contracts must remain explicit even though optimizer execution is out of scope for v1.

```text
MySQL query result or ../ARX/greenhouse_data.csv snapshot
        |
        v
Ingestion + validation + preprocessing
        |
        v
Chronological split + optional ARX retraining
        |
        v
Prediction adapter
        |
        v
Adaptive Kalman-ready update block
        |
        +--> MySQL experiment storage
        |
        +--> Vite dashboard / plots
        |
        +--> Evaluation metrics and exports
```

---

## Tech Stack

| Layer | Technology | Version | Why Chosen |
|-------|------------|---------|------------|
| Frontend | Vite + React 19 + TypeScript | 6.x / 19.x | Lightweight dashboard; fast HMR |
| Styling | Tailwind CSS v4 | 4.x | Utility-first; co-located with component |
| Charting | Recharts | 2.x | Composable React charting; accessible SVG |
| Data fetching | TanStack Query | 5.x | Server-state caching and refetch |
| Frontend testing | Vitest + Testing Library | 4.x / 16.x | jsdom unit tests collocated with code |
| Backend | Python / Django | 4.x | Python fits ARX/Kalman work; Django ORM selected for persistence |
| REST API | Django REST Framework | 3.15+ | Serializer/view layer for dashboard API |
| CORS | django-cors-headers | 4.x | Dev proxy bypass for Vite dev server |
| Database | MySQL from XAMPP | 8.x | Local development database already chosen by project owner |
| ORM | Django ORM | 4.x | Structured persistence and query layer for experiment logs |
| Auth | TBD | TBD | Needed for authorized configuration changes |
| Hosting | AWS | TBD | Deployment target selected; exact service still open |
| CI/CD | TBD | TBD | Not required for initial local validation |

---

## System Components

### Frontend Architecture

The dashboard is a single-page Vite + React + TypeScript application located at `Kalman/dashboard/`.
It proxies `/api/*` to the Django dev server at `127.0.0.1:8000`.

**Routing**: None (single-page; run selected via sidebar).

**State management**: TanStack Query for server state; local `useState` for UI controls.

**Component structure**:

```text
dashboard/src/
  api/
    client.ts        – fetch helpers for /api/runs/, /series/, /metrics/
    types.ts         – TypeScript types matching DRF serializers
  components/
    RunSelector.tsx  – sidebar list with status dot
    SliceChart.tsx   – three-series Recharts line chart (raw/ARX/KF)
    AdaptiveStatusBar.tsx – R_updated / R_skipped / skipped counts
    MetricsPanel.tsx – per-slice metrics table with acceptance gate
    RunDashboard.tsx – composes chart + bar + metrics for one run
  __tests__/         – Vitest + Testing Library unit tests
  test/setup.ts      – jest-dom + ResizeObserver mock
  App.tsx            – QueryClientProvider + sidebar + main layout
src/components/
  ui/
  features/
  layouts/
```

**Data fetching pattern**: TBD.

---

### Backend Architecture

This section remains a template until the Django/backend implementation begins.

**API style**: TBD.

**Middleware stack**:
1. Authentication and authorization for configuration changes.
2. Request validation for incoming sensor and experiment configuration payloads.
3. Error handler for consistent pipeline and API errors.

**Service layer pattern**: Keep preprocessing, split/replay orchestration, prediction adapter, Adaptive Kalman-ready estimator, storage, evaluation, and future AMPC controller logic as separate modules.

---

### Infrastructure

**Environments**:

| Environment | URL | Branch | Notes |
|-------------|-----|--------|-------|
| Production | TBD | TBD | AWS target, exact service not chosen |
| Local | `localhost` | any | npm frontend commands, Python/Django backend, XAMPP MySQL |

**CI/CD**: TBD.

---

## Data Flow

### Core v1 Estimation Flow

```text
1. Load a time-series dataset from MySQL or from the current CSV snapshot.
2. Sort by timestamp and apply chronological split: train 60%, validation 20%, test 20%.
3. Validate timestamp and variable fields, then apply preprocessing policy for missing, malformed, repeated, or out-of-range values.
4. Retrain or reload the ARX artifact from the train slice for the selected run.
5. Use the validation slice to tune fixed-per-run parameters such as `Q` and preprocessing choices.
6. Replay the frozen ARX plus Adaptive Kalman configuration on the held-out test slice.
7. For each cycle, use ARX prediction as the estimator prior for scalar `Soil_Moisture`.
8. Run bounded innovation-driven adaptive `R` update, Kalman gain calculation, and scalar measurement update.
9. Store timestamp, raw measurement, prediction output, filtered estimate, innovation/residual, `P`, `R`, config, and status.
10. Visualize raw, predicted, and filtered series.
11. Produce held-out evaluation metrics and report-ready exports.
```

---

## Prediction Adapter Contract

The prediction layer is deliberately separated from the Kalman estimator by an
abstract interface.  This keeps model choice decoupled from estimator code and
allows future adapters (LightGBM, XGBoost, LSTM, …) to slot in without touching
any downstream code.

### Interface (`estimation.prediction`)

```python
# estimation/prediction/base.py

class PredictionAdapter(ABC):
    @property @abstractmethod
    def model_kind(self) -> str: ...          # "arx", "lightgbm", …

    @property @abstractmethod
    def is_trained(self) -> bool: ...

    @property @abstractmethod
    def min_history_len(self) -> int: ...     # records required for one prediction

    @abstractmethod
    def train(
        self,
        records: Sequence[ProcessedRecord],
        *,
        val_records: Sequence[ProcessedRecord] | None = None,
    ) -> dict[str, object]: ...              # summary incl. train/val metrics

    @abstractmethod
    def predict(self, inp: PredictionInput) -> PredictionResult: ...

    @abstractmethod
    def save_artifact(self, path: Path) -> None: ...

    @classmethod @abstractmethod
    def load_artifact(cls, path: Path) -> "PredictionAdapter": ...
```

**`PredictionInput`** — mutable dataclass wrapping `list[ProcessedRecord]`.
Callers populate `history` with the window of recent preprocessed records.

**`PredictionResult`** — frozen dataclass with fields:

| Field | Type | Meaning |
|-------|------|---------|
| `value` | `float \| None` | Predicted next-step `Soil_Moisture`; `None` when unavailable |
| `status` | `str` | `"ok"`, `"unavailable"`, or `"error"` |
| `model_kind` | `str` | Mirrors `adapter.model_kind` |
| `reason` | `str` | Human-readable explanation when not `"ok"` |

`predict()` **never raises** — all error conditions are surfaced through
`status="error"` / `status="unavailable"` so the Kalman estimator can always
decide whether to proceed with a measurement-only update.

### v1 Baseline — ARX (OLS)

`ARXPredictionAdapter` implements the contract using an offline OLS-fitted
ARX(*na*, *nb*, *nk*) model.  Default orders: *na* = 2, *nb* = 2, *nk* = 1.

Training constructs the regression matrix from `ProcessedRecord` arrays and
solves via `numpy.linalg.lstsq`.  Training summary includes RMSE, MAE, R²,
and optional validation-slice metrics.

Artifacts are persisted as JSON and can be loaded back with
`ARXPredictionAdapter.load_artifact(path)`.  The loader also handles the
legacy format produced by `../ARX/arx_pipeline.py`, including the
`best_candidate` envelope.

Public module exports:

```python
from estimation.prediction import (
    PredictionInput,
    PredictionResult,
    PredictionAdapter,
    ARXTrainConfig,
    ARXPredictionAdapter,
)
```

### Extending with a New Adapter

1. Subclass `PredictionAdapter`.
2. Implement all six abstract members.
3. Keep `model_kind` a stable slug (e.g. `"lightgbm"`).
4. Ensure `predict()` never raises.
5. Register the adapter in the run-configuration (task #008).

---

## Adaptive Kalman Cycle (`estimation.kalman`)

The `estimation.kalman` package provides the v1 scalar state-estimator for
`Soil_Moisture`.  It consumes the output of the prediction adapter and a raw
preprocessed measurement to produce a filtered estimate each cycle.

### Module public API

```python
from estimation.kalman import (
    KalmanConfig,   # frozen hyperparameter dataclass
    KalmanState,    # mutable runtime state
    CycleResult,    # frozen per-cycle output record
    AdaptiveKalmanCycle,  # orchestrates prediction + update
)
```

### Data contracts

**`KalmanConfig`** — frozen dataclass (hyperparameters, validated in `__post_init__`):

| Field | Default | Meaning |
|-------|---------|---------|
| `x0` | 0.0 | Initial state estimate |
| `P0` | 1.0 | Initial error covariance |
| `Q` | 0.05 | Process noise (fixed per run) |
| `R0` | 1.0 | Initial measurement noise |
| `R_min` | 0.05 | Lower bound for adaptive R |
| `R_max` | 25.0 | Upper bound for adaptive R |
| `alpha` | 0.95 | EMA decay for adaptive R |

**`KalmanState`** — mutable dataclass updated in-place each cycle:
`x_post`, `P_post`, `R`, `step`.

**`CycleResult`** — frozen per-cycle output; contains the Kalman subset needed to populate `PipelineCycle` (Task #007 mapper adds run-level metadata, `kf_` prefixes, etc.):

| Field | Type | Meaning |
|-------|------|---------|
| `timestamp` | `datetime` | Record timestamp |
| `cycle_index` | `int` | Sequential cycle counter |
| `raw_soil_moisture` | `float \| None` | Raw measurement |
| `preprocess_status` | `str` | From `ProcessedRecord` |
| `arx_predicted` | `float \| None` | ARX prior (`None` if unavailable) |
| `x_prior` | `float` | Time-update prediction (ARX or propagated) |
| `P_prior` | `float` | Prior error covariance |
| `innovation` | `float \| None` | `z_k - x_prior`; `None` if skipped |
| `R` | `float` | Current adaptive measurement noise |
| `K` | `float \| None` | Kalman gain; `None` if skipped |
| `x_posterior` | `float` | Filtered state estimate |
| `P_posterior` | `float` | Posterior error covariance |
| `cycle_status` | `str` | `"ok"` / `"skipped_no_measurement"` / `"error"` |
| `adaptive_status` | `str` | `"R_updated"` (measurement processed) / `"R_skipped"` (no measurement) / `"skipped"` (error branch) |
| `latency_ms` | `float \| None` | Wall-clock time for this cycle |
| `error_message` | `str \| None` | Populated on `"error"` status only |

### Estimation cycle (one step)

```text
1. Obtain ARX prior via PredictionAdapter (if trained and history sufficient)
   — falls back to last posterior if adapter unavailable / prediction fails
2. Time update:  x_prior = arx_predicted OR x_post_prev
                 P_prior = P_post_prev + Q
3. Measurement check:
   — if measurement absent or status == "skipped":
       x_post = x_prior, P_post = P_prior, R unchanged → status "skipped_no_measurement"
   — else (measurement z available):
4. Innovation:  e = z - x_prior
5. Adaptive R:  R_new = alpha * R + (1 - alpha) * e²   → clip to [R_min, R_max]
6. Kalman gain: K = P_prior / (P_prior + R_new)
7. Update:      x_post = x_prior + K * e
                P_post = (1 - K) * P_prior              (guarantees P_post < P_prior)
8. Emit CycleResult with all internals logged
```

### "Never raises" contract

`AdaptiveKalmanCycle.step()` catches all exceptions internally.  On failure it
returns a `CycleResult` with `cycle_status="error"` and an `error_message`, and
**preserves the last known good state**.  The pipeline is never interrupted by a
single bad record.

### Adapter integration

`AdaptiveKalmanCycle.__init__` accepts an optional `adapter: PredictionAdapter`.
History of preprocessed records is maintained internally and fed to the adapter
for causal predictions.  Before `min_history_len` records have accumulated, the
prior falls back to the last posterior (`x_post`).

---

## Experiment Configuration (`estimation.run_config`)

Task #006 adds a central configuration layer so that experiment parameters are
never scattered as hard-coded constants.  Every run starts from an explicit
``RunConfig`` object that is persisted atomically alongside the run row.

### Module public API

```python
from estimation.run_config import (
    RunConfig,           # frozen in-memory configuration object
    ConfigFrozenError,   # raised on mutation attempts after run start
    create_run,          # persist RunConfig → ExperimentRun + ExperimentConfig
    load_config,         # reconstruct RunConfig from a saved run id
    update_config,       # replace a pending run's config
)
```

### `RunConfig` fields

| Field | Default | Meaning |
|-------|---------|---------|
| `name` | `"unnamed_run"` | Human-readable run label |
| `dataset_source` | `""` | CSV path or MySQL query description |
| `x0` … `alpha` | ADR-003 | Kalman parameters — validated via `KalmanConfig` |
| `train_ratio` | 0.60 | Chronological split ratios (must sum to 1.0) |
| `val_ratio` | 0.20 | |
| `test_ratio` | 0.20 | |
| `arx_na`, `arx_nb`, `arx_nk` | 2, 2, 1 | ARX model orders — validated via `ARXTrainConfig` |
| `arx_input_cols` | all 6 sensor cols | Ordered tuple of ARX input column names |
| `preprocessing_policy` | `"keep_last"` | `"keep_last"` / `"interpolate"` / `"skip"` |

`RunConfig` is a **frozen dataclass**; mutation after construction raises
`TypeError`.  Validation delegates to `KalmanConfig` and `ARXTrainConfig` for
their respective fields, and adds `math.isfinite()` guards for all float fields.

### v1 authorization model

Configuration changes are blocked once `ExperimentRun.status` moves out of
`"pending"`.  Calling `update_config()` on a non-pending run raises
`ConfigFrozenError`.  There is no role-based auth in v1; this is a hard
service-layer invariant documented as a TODO for future auth integration.

### Persistence model

```text
RunConfig
  │
  ├── create_run()  ──► ExperimentRun  (status="pending")
  │                       │
  │                       └── ExperimentConfig (one-to-one)
  │                               ├── structured columns (x0, P0, …)
  │                               └── raw_config_json  (full JSON snapshot)
  │
  ├── load_config(run_id)  ◄── ExperimentConfig.from_experiment_config()
  │
  └── update_config(run_id, cfg)  ──► overwrites ExperimentConfig + refreshes JSON
                                       raises ConfigFrozenError if not pending
```

`raw_config_json` stores a complete JSON snapshot of `RunConfig` so a saved
row is fully self-describing.  `RunConfig.to_json()` / `from_json()` provide
the round-trip.  `to_kalman_config()` and `to_arx_train_config()` extract the
corresponding validated sub-configs for the estimation and prediction modules.

---

## Pipeline Storage (`estimation.pipeline`)

Implemented in Task #007.  The storage layer sits between the Kalman estimation
cycle and the database: it maps `CycleResult` objects to `PipelineCycle` rows
and manages the `ExperimentRun` lifecycle.

### Package layout

```
estimation/pipeline/
    __init__.py   — public API re-exports
    store.py      — mapping, bulk persistence, run lifecycle
```

### Public API

| Symbol | Type | Purpose |
|--------|------|---------|
| `map_result_to_cycle` | pure function | Maps `CycleResult` + run metadata → unsaved `PipelineCycle` |
| `bulk_save_cycles` | DB function | Batch-inserts unsaved `PipelineCycle` instances |
| `begin_run` | DB function | Transitions `ExperimentRun` PENDING → RUNNING |
| `end_run` | DB function | Transitions `ExperimentRun` RUNNING → COMPLETED / FAILED / ABORTED |
| `RunStateError` | exception | Raised on invalid status transitions |

### Field mapping — `CycleResult` → `PipelineCycle`

| `CycleResult` field | `PipelineCycle` column | Notes |
|---------------------|------------------------|-------|
| `timestamp` | `sample_ts` | Source timestamp |
| `cycle_index` | `cycle_index` | 0-based index within run |
| `raw_soil_moisture` | `raw_soil_moisture` | From `CycleResult` (not `ProcessedRecord`) |
| `preprocess_status` | `preprocess_status` | `"valid"` / `"kept_last"` / `"interpolated"` / `"skipped"` / `"invalid"` |
| `arx_predicted` | `arx_predicted` | NULL when prediction unavailable |
| `x_prior` | `kf_x_prior` | Prior estimate `x̂⁻ₖ` |
| `P_prior` | `kf_P_prior` | Prior covariance `P̂⁻ₖ` |
| `innovation` | `kf_innovation` | `eₖ = zₖ − x̂⁻ₖ`; NULL on skipped steps |
| `R` | `kf_R` | Adaptive measurement noise `Rₖ` |
| `K` | `kf_K` | Kalman gain `Kₖ`; NULL on skipped steps |
| `x_posterior` | `kf_x_posterior` | Filtered estimate `x̂ₖ` |
| `P_posterior` | `kf_P_posterior` | Updated covariance `Pₖ` |
| `adaptive_status` | `adaptive_status` | `"R_updated"` / `"R_skipped"` / `"skipped"` |
| `cycle_status` | `cycle_status` | `"ok"` / `"skipped_no_measurement"` / `"skipped_invalid"` / `"error"` |
| `error_message` | `error_message` | Non-NULL only on `"error"` cycles |

Run-level metadata (`run`, `slice_type`, `source_type`) is supplied by the caller
as arguments to `map_result_to_cycle`.

When a `ProcessedRecord` is passed as the optional `record` argument, the raw
sensor readings (`raw_temperature`, `raw_humidity`, `raw_light`, `raw_drip`,
`raw_mist`, `raw_fan`) are also populated for full traceability.

### Run lifecycle

```text
create_run(cfg)               ──► ExperimentRun (status="pending")
   │
   ├── begin_run(run)         ──► status="running",  started_at=now()
   │       raises RunStateError if not "pending"
   │
   ├── [bulk_save_cycles ×N]  ──► PipelineCycle rows in DB
   │
   └── end_run(run, status)   ──► status="completed"|"failed"|"aborted",
           completed_at=now()      raises RunStateError if not "running"
```

Status transitions use a conditional `QuerySet.update` (one UPDATE query) so
concurrent calls cannot silently corrupt state.

### Traceability chain

Every `PipelineCycle` row carries a FK to `ExperimentRun`, which in turn has a
one-to-one `ExperimentConfig` with the full configuration snapshot.  Any cycle
can therefore be traced to:

* its raw input values (raw sensor columns)
* its ARX prediction
* all Kalman internals at that step
* the exact configuration used (via `run.config`)

Pipeline failures and skipped updates are stored as explicit rows with
`cycle_status="error"` (+ non-null `error_message`) or
`cycle_status="skipped_no_measurement"`, never silently dropped.

Also, `latency_ms` from `CycleResult` is persisted in `PipelineCycle.latency_ms` (nullable
`FloatField`) to enable per-cycle performance tracing.

---

## Evaluation Module (`estimation.evaluation`)

Implemented in Task #008.  The evaluation layer computes aggregated metrics from
`PipelineCycle` rows, persists them to `EvaluationSummary`, and generates
report-ready exports.

### Package layout

```
estimation/evaluation/
    __init__.py   — public API (pure metrics importable without Django)
    metrics.py    — SliceMetrics dataclass + compute_metrics() pure function
    reporter.py   — DB integration, evaluate_slice/all_slices, text/CSV/plot export
```

### Public API

| Symbol | Type | Purpose |
|--------|------|---------|
| `SliceMetrics` | frozen dataclass | All computed metrics for one data slice |
| `compute_metrics(rows)` | pure function | Compute metrics from a list of cycle-row dicts |
| `VARIANCE_REDUCTION_MIN` | constant `0.20` | ADR-003 acceptance threshold |
| `RMSE_RATIO_MAX` | constant `1.05` | ADR-003 acceptance threshold |
| `MAE_RATIO_MAX` | constant `1.05` | ADR-003 acceptance threshold |
| `evaluate_slice(run_pk, slice_type)` | DB function | Compute → persist → return `EvaluationSummary` |
| `evaluate_all_slices(run_pk)` | DB function | Evaluate all three slices; returns `dict[str, EvaluationSummary]` |
| `build_text_report(run_pk)` | export | Human-readable multi-section text report |
| `export_to_csv(run_pk, output_path)` | export | CSV with one row per slice; returns resolved `Path` |
| `export_plots(run_pk, output_dir)` | export | PNG diagnostics (requires `matplotlib`); returns `list[Path]` |

### SliceMetrics fields

| Field | Description |
|-------|-------------|
| `n_samples` | Total cycles in the slice |
| `n_valid` | Cycles with `cycle_status="ok"` |
| `n_skipped` | Cycles with `cycle_status` starting with `"skipped"` |
| `n_error` | Cycles with `cycle_status="error"` |
| `n_r_updated` | Adaptive status `"R_updated"` count |
| `n_r_skipped` | Adaptive status `"R_skipped"` count |
| `n_adaptive_skipped` | Adaptive status `"skipped"` (error path) count |
| `latency_mean_ms` | Mean per-cycle wall-clock time |
| `latency_p95_ms` | 95th-percentile per-cycle wall-clock time |
| `rmse_arx` / `mae_arx` | ARX prediction accuracy vs raw reference |
| `rmse_filtered` / `mae_filtered` | Kalman filter accuracy vs raw reference |
| `variance_reduction` | `1 − var(diff(filtered)) / var(diff(raw))` |
| `rmse_ratio` / `mae_ratio` | Guardrail: `rmse_filtered / rmse_arx` |
| `innovation_mean` / `_std` / `_max_abs` | Innovation sequence diagnostics |
| `R_mean` / `_min_observed` / `_max_observed` | Adaptive R diagnostics |
| `P_mean` / `P_max` | Posterior covariance diagnostics |
| `pass_variance_reduction` | `variance_reduction >= 0.20` |
| `pass_rmse_guardrail` | `rmse_ratio <= 1.05` |
| `pass_mae_guardrail` | `mae_ratio <= 1.05` |
| `passes_acceptance_gate` | All three ADR-003 flags are `True` |
| `cycle_success_rate` *(property)* | `n_valid / n_samples` |
| `sample_loss_rate` *(property)* | `(n_skipped + n_error) / n_samples` |

### Django coupling and lazy imports

`estimation.evaluation.metrics` has **no Django dependency** and can be imported
in any context (e.g. standalone scripts, pure unit tests) without setting
`DJANGO_SETTINGS_MODULE`.  The DB-backed functions in `reporter.py` are imported
lazily via `__getattr__` in the package `__init__.py`, mirroring the same pattern
used by `estimation.run_config`.

### Report structure (`build_text_report`)

The text report contains the following sections (columns: Train / Validation / Test):

1. Sample counts & cycle success rate / sample loss rate
2. Latency (mean + P95)
3. ARX baseline accuracy (RMSE, MAE)
4. Kalman filter accuracy (RMSE, MAE, guardrail ratios)
5. Variance reduction (ADR-003)
6. Innovation diagnostics
7. Adaptive R diagnostics
8. Posterior covariance
9. **ADR-003 acceptance gate** (Test slice only) — PASS / FAIL per criterion
10. AMPC readiness placeholder

### Plot export (`export_plots`)

Requires `matplotlib >= 3.8` (optional; gracefully skipped if unavailable or if
the installed `matplotlib` was compiled against a different NumPy ABI).  Produces
four PNGs per slice:

| File | Contents |
|------|---------|
| `time_series_{slice}.png` | Raw / ARX predicted / Kalman filtered over time |
| `innovation_{slice}.png` | Innovation sequence `eₖ` over time |
| `adaptive_R_{slice}.png` | Adaptive measurement noise `Rₖ` over time |
| `residuals_{slice}.png` | Histogram of `raw − filtered` residuals |

---

## AMPC-Ready Modeling Boundary

The AMPC controller is not the first implementation target, but the architecture must preserve these contracts:

| Concept | Candidate v1 meaning | Notes |
|---------|----------------------|-------|
| State | Estimation state = soil moisture `theta`; AMPC-ready control state = root-zone depletion `Dr` | v1 estimation is scalar `Soil_Moisture`; `Dr` stays documented for later controller synthesis |
| Control input | Drip/pump seconds, mist seconds, fan duration/level | Full autonomous scheduling remains gated |
| Disturbances | ET0/ETc, temperature, humidity, light | Use available dataset fields first |
| Output | Soil moisture sensor and selected environment variables | Must stay traceable to raw measurements |
| Cost terms | Zone/range tracking, water/energy penalty, actuator switching, `Delta u` smoothing | Documented before optimizer implementation |
| Safety constraints | Soil moisture bounds, RH max, daily water cap, no mist at high RH/night, sensor-fault fallback | Required for later AMPC control design |

For the current research synthesis, see [`ADAPTIVE_KALMAN_AMPC_NOTES.md`](./ADAPTIVE_KALMAN_AMPC_NOTES.md).

---

## Design system and UX

The canonical design system and UX flow summaries live in [`DESIGN_SYSTEM.md`](./DESIGN_SYSTEM.md). Do not duplicate design tokens here.

---

## Security Architecture

**Authentication model**: TBD.

**Authorization**: Configuration changes must be restricted to authorized users.

**Data protection**:
- No secrets or credentials committed to the repository.
- Operational endpoints must not be exposed publicly without authentication.

**Key security decisions**: See `docs/technical/DECISIONS.md`.

---

## Performance Considerations

- Prediction plus Adaptive Kalman-ready update target: <= 500 ms per cycle on replay, excluding explicit offline ARX retraining.
- Dashboard/output update target: <= 5 seconds.
- The pipeline should continue operating through short missing/noisy data windows.
- Held-out replay must achieve at least 20% first-difference variance reduction with 30% as target, while filtered RMSE/MAE do not degrade more than 5% versus ARX prediction.

---

## Testing and data robustness

Automated coverage for bad or noisy inputs lives in `Kalman/backend/estimation/tests/test_pipeline_robustness.py` (task **#011**). It exercises CSV loading (including malformed numerics and skipped timestamp rows), `validate_batch` with explicit validation statuses and non-empty `reason` for out-of-range and suspicious-repeat cases, preprocessing policies (`keep_last`, `interpolate`, `skip`), and full `AdaptiveKalmanCycle.replay` on synthetic rows and on slices derived from `../ARX/greenhouse_data.csv` with injected defects. The suite asserts the pipeline does not crash, per-sample preprocess statuses stay in the allowed set, and cycle-level errors surface an `error_message` when `cycle_status == "error"`.

Run: `python -m pytest estimation/tests/test_pipeline_robustness.py` from `Kalman/backend`.

---

## Known Constraints and Technical Debt

| Item | Impact | Plan |
|------|--------|------|
| Node version not pinned | Local frontend results may vary across machines | Add `.nvmrc` or package engine constraint later |
| AWS service not chosen | Deployment architecture remains incomplete | Decide AWS target before deployment task |
| Django/backend scaffolding not created yet | Architecture is agreed but implementation entrypoints are still missing | Create during backend tasks |
| Storage schema details not finalized | Logging implementation still needs concrete table design and export policy | Resolve in task #002 |
| AMPC controller implementation scope intentionally deferred | Docs must preserve AMPC contracts without forcing full closed-loop actuation too early | Keep deferred until after task #013 |
