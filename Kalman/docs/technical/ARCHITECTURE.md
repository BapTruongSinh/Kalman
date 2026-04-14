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

The v1 system is a greenhouse state-estimation pipeline oriented toward Adaptive Kalman plus AMPC. It accepts either offline records from `../ARX/greenhouse_data.csv` or later live sensor records, validates and preprocesses those records, asks a prediction adapter for a next-step prediction, uses the estimator module for an Adaptive Kalman-ready update with the real measurement, then stores and visualizes raw, predicted, and filtered values.

The core architectural decision is to keep v1 staged while preventing a wrong baseline-only design. Full closed-loop AMPC actuation and cloud-scale operations are postponed until the prediction plus Adaptive Kalman foundation is validated, but AMPC state/control/disturbance/cost/safety contracts must remain explicit.

```text
../ARX/greenhouse_data.csv or sensors
        |
        v
Ingestion + validation + preprocessing
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

**Service layer pattern**: Keep preprocessing, prediction adapter, Adaptive Kalman-ready estimator, storage, evaluation, and future AMPC controller logic as separate modules.

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
1. Load a row from ../ARX/greenhouse_data.csv or receive a sensor sample.
2. Validate timestamp and variable fields.
3. Apply preprocessing policy for missing, malformed, repeated, or out-of-range values.
4. Send the validated state/history to the prediction adapter. ARX is the first baseline adapter.
5. Use prediction output as the estimator prediction input.
6. Run Adaptive Kalman-ready uncertainty propagation and measurement update.
7. Store raw measurement, prediction output, filtered estimate, residual/innovation, covariance or adaptive status, timestamp, config, and status.
8. Visualize raw, predicted, and filtered series.
9. Produce evaluation metrics and report-ready exports.
```

---

## AMPC-Ready Modeling Boundary

The AMPC controller is not the first implementation target, but the architecture must preserve these contracts:

| Concept | Candidate v1 meaning | Notes |
|---------|----------------------|-------|
| State | Soil moisture `theta` or root-zone depletion `Dr` | Task #001 chooses the first estimator target |
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

- Prediction plus Adaptive Kalman-ready update target: <= 500 ms per cycle.
- Dashboard/output update target: <= 5 seconds.
- The pipeline should continue operating through short missing/noisy data windows.

---

## Known Constraints and Technical Debt

| Item | Impact | Plan |
|------|--------|------|
| Node version not pinned | Local frontend results may vary across machines | Add `.nvmrc` or package engine constraint later |
| AWS service not chosen | Deployment architecture remains incomplete | Decide AWS target before deployment task |
| Adaptive Kalman variable and adaptive rule scope not finalized | Backend implementation may branch between single-variable, `Dr`, and covariance-adaptation approaches | Resolve in task #001 |
| Storage format not finalized | Logging implementation may need MySQL plus CSV export or MySQL only | Resolve in task #001 and #002 |
| AMPC controller implementation scope not finalized | Docs must preserve AMPC contracts without forcing full closed-loop actuation too early | Resolve in task #001 and task #013 |
