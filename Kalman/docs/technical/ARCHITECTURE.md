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
