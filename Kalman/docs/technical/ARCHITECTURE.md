<!--
DOCUMENT METADATA
Owner: @systems-architect
Update trigger: System architecture changes, new integrations, component additions
Read by: All agents. Always read before making implementation decisions.
For design tokens, component specs, and UX flows see DESIGN_SYSTEM.md.
-->

# System Architecture

> Last updated: 2026-04-14
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
| Frontend | Vite | TBD | Lightweight dashboard and charting shell |
| Styling | TBD | TBD | Design system not finalized for v1 |
| Backend | Python / Django | TBD | Python fits ARX/Kalman work; Django ORM selected for persistence |
| Database | MySQL from XAMPP | TBD | Local development database already chosen by project owner |
| ORM | Django ORM | TBD | Structured persistence and query layer for experiment logs |
| Auth | TBD | TBD | Needed for authorized configuration changes |
| Hosting | AWS | TBD | Deployment target selected; exact service still open |
| CI/CD | TBD | TBD | Not required for initial local validation |

---

## System Components

### Frontend Architecture

This section remains a template until the dashboard implementation begins.

**Routing**: TBD.

**State management**: TBD.

**Component structure**:

```text
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

## Known Constraints and Technical Debt

| Item | Impact | Plan |
|------|--------|------|
| Node version not pinned | Local frontend results may vary across machines | Add `.nvmrc` or package engine constraint later |
| AWS service not chosen | Deployment architecture remains incomplete | Decide AWS target before deployment task |
| Django/backend scaffolding not created yet | Architecture is agreed but implementation entrypoints are still missing | Create during backend tasks |
| Storage schema details not finalized | Logging implementation still needs concrete table design and export policy | Resolve in task #002 |
| AMPC controller implementation scope intentionally deferred | Docs must preserve AMPC contracts without forcing full closed-loop actuation too early | Keep deferred until after task #013 |
