# Product Requirements Document

> [!WARNING]
> **READ-ONLY FOR ALL AGENTS**
> This document is the source of truth for what we are building.
> Claude agents must read this document to understand requirements.
> Do not edit it without explicit human instruction.

---

**Version**: 1.1
**Status**: Draft
**Last updated by human**: 2026-04-14
**Product owner**: Project owner

---

## 1. Executive Summary

The project target is a smart greenhouse system built around Adaptive Kalman estimation and AMPC. v1 is intentionally staged: validate the state-estimation and prediction foundation first, while documenting AMPC-ready state, control, disturbance, cost, and safety boundaries so later controller work does not require a redesign. The system uses the existing `../ARX/` folder and `../ARX/greenhouse_data.csv` as the initial foundation for development, replay, tuning, evaluation, and baseline visualization. A successful v1 proves that the pipeline can process greenhouse measurements, run prediction-assisted Adaptive Kalman-ready updates, store traceable outputs, and produce measurable evidence that filtered signals are more stable and useful than raw signals.

---

## 2. Problem Statement

### 2.1 Current Situation

Without this system, greenhouse control is usually based on manual observation, separate sensor readings, and simple threshold-based actions. A user may turn on a pump when soil looks dry or turn on a fan when air feels too humid. These methods are slow, inconsistent, and unable to anticipate future changes in a coupled greenhouse environment.

### 2.2 The Problem

Soil moisture, air temperature, relative humidity, and light intensity change continuously and influence one another. Raw sensor readings can be noisy, incomplete, delayed, or temporarily invalid. If decisions or analysis are based directly on those readings, the user may react to noise instead of the real greenhouse state, wasting water or energy and creating unstable growing conditions.

v1 must solve the estimation problem first: build a reliable pipeline that turns raw or replayed data into prediction outputs, Adaptive Kalman-ready estimates, residual diagnostics, and report-ready evaluation outputs. It must also preserve the AMPC interpretation of greenhouse state, disturbances, and actuator inputs so estimation results can feed control design later.

### 2.3 Why Now

The repository already includes ARX work, a greenhouse dataset, and additional research notes about Adaptive Kalman, FAO-56, AMPC cost functions, and constraints. Starting with offline data and an Adaptive Kalman-ready pipeline reduces implementation risk before live sensor streaming or closed-loop AMPC actuation is added. This staged approach makes the project academically defendable and technically extensible.

---

## 3. Goals & Success Metrics

### 3.1 Goals

- Prove that the prediction-assisted Adaptive Kalman-ready pipeline runs correctly and consistently from input through evaluation.
- Show that the filtered signal is smoother and more useful than raw measurements alone without hiding residual instability.
- Preserve enough traceability to explain each filtered value from its raw measurement, prediction output, timestamp, residual/innovation, adaptive status, and configuration context.
- Create a foundation that can be extended to AMPC using explicit state, control, disturbance, cost, and safety contracts.

### 3.2 Success Metrics

| Metric | Baseline | Target | How Measured |
|--------|----------|--------|--------------|
| Pipeline cycle success rate | TBD | >= 95% | Successful prediction-update cycles over valid samples |
| Prediction + Adaptive Kalman-ready cycle latency | TBD | <= 500 ms | Timed execution under normal prototype conditions |
| Output update delay | TBD | <= 5 seconds | Time from input arrival to display or log update |
| Sample loss over long run | TBD | < 2% over 24 hours | Count missing or dropped samples over a long test run |
| Variance reduction | Raw signal variance | 20-30% reduction | Compare raw vs filtered signal variance |
| Residual stability | TBD | No persistent exploding behavior | Residual or innovation time-series analysis |
| Adaptive estimator traceability | TBD | Adaptive status or rationale logged per affected cycle | Estimator diagnostics and configuration records |
| AMPC readiness | TBD | State/control/disturbance/cost/safety contract documented | Architecture and task acceptance review |
| Visualization completeness | TBD | Raw, prediction output, and filtered curves viewable | Dashboard or generated plots |
| Logging completeness | TBD | Raw measurement, prediction output, filtered estimate, timestamp, residual/innovation, adaptive status per cycle | Stored experiment records |
| Robustness to imperfect data | TBD | No full crash on short missing/noisy data | Missing/noisy-data test cases |
| Reproducible evaluation | TBD | Same dataset and config regenerate consistent results | Replay `../ARX/greenhouse_data.csv` with saved config |

---

## 4. User Personas

### Persona: Project Owner

- **Role**: Developer, researcher, and decision maker for the prototype.
- **Goals**: Build a defendable v1 estimation pipeline; evaluate Adaptive Kalman-ready estimator quality; prepare the system for AMPC.
- **Pain points**: Manual greenhouse observation is reactive and inconsistent; raw signals are noisy; threshold-based control does not prove a reliable state estimate.
- **Technical level**: Developer / technical.
- **Usage frequency**: Frequent during development, testing, demonstrations, and reporting.

---

## 5. Functional Requirements

### 5.1 Data Input

- **FR-001**: The system must support offline or batch loading from `../ARX/greenhouse_data.csv`.
- **FR-002**: The system must be able to support real sensor stream ingestion for later live testing.
- **FR-003**: Each input record must preserve a timestamp and variable identifiers for available fields such as `Soil_Moisture`, `Temperature`, `Humidity`, `Light`, `Drip`, `Mist`, and `Fan`.

### 5.2 Validation and Preprocessing

- **FR-004**: The pipeline must validate missing values, malformed values, out-of-range values, and suspicious repeated values before data reaches the filter.
- **FR-005**: The pipeline must support basic preprocessing policies such as keeping the last valid sample, skipping a measurement update, or applying simple interpolation when appropriate.
- **FR-006**: Corrected, skipped, interpolated, or invalid samples must carry an explicit status for later analysis.

### 5.3 Prediction Model Boundary

- **FR-007**: The system must reuse the existing ARX work in `../ARX/` as the initial retrainable offline prediction baseline where practical.
- **FR-007a**: v1 should support explicit offline ARX retraining from `../ARX/greenhouse_data.csv` or a selected compatible CSV, then persist the trained coefficients/artifact used by the Kalman run.
- **FR-008**: The prediction block must output the predicted next-step state or output needed by the estimator update step.
- **FR-009**: The integration must keep prediction and estimation modules loosely coupled so ARX can be replaced or compared later with alternatives such as LightGBM or XGBoost.

### 5.4 Adaptive Kalman-ready Filtering

- **FR-010**: The system must execute a complete estimator cycle for each processed time step: prediction, uncertainty propagation, measurement update, and filtered-state output.
- **FR-011**: The estimator pipeline must continue operating when short runs of measurements are missing, noisy, or temporarily invalid.
- **FR-012**: The pipeline must expose residuals or innovations for diagnostics.
- **FR-023**: The estimator design must support a minimal Adaptive Kalman mechanism to be finalized in task #001, such as bounded innovation-driven `Q`/`R` adjustment or an explicitly documented non-adaptive fallback.
- **FR-024**: Any adaptive behavior must be logged with status, parameter values or rationale, and bounds so report outputs remain explainable.

### 5.5 AMPC Readiness

- **FR-025**: The architecture must preserve AMPC-ready contracts for candidate state variables such as soil moisture `theta` or root-zone depletion `Dr`, actuator control inputs such as drip/mist/fan duration, and disturbances such as ET0/ETc, temperature, humidity, and light.
- **FR-026**: The system documentation must maintain candidate AMPC cost terms and constraints, including zone/range tracking, water or energy penalties, actuator switching penalties, daily water caps, humidity limits, and sensor-fault/emergency fallback rules.
- **FR-027**: The v1 implementation must not hardwire assumptions that prevent later AMPC optimization or model replacement.

### 5.6 Storage and Logging

- **FR-013**: The system must store raw measurements, prediction outputs, filtered estimates, residuals/innovations, adaptive status, timestamps, and pipeline status logs.
- **FR-014**: Raw data, prediction outputs, and filtered estimates must be stored separately or clearly labeled.
- **FR-015**: Each experiment run must preserve the configuration used to generate its outputs.

### 5.7 Configuration

- **FR-016**: The system must allow adjustment of sampling time, initial state assumptions, covariance-related parameters, adaptive-estimator bounds/rules, and prediction model settings without rewriting core code.
- **FR-017**: Configuration changes must be restricted to authorized users.

### 5.8 Visualization

- **FR-018**: The system must visualize or generate plots comparing raw sensor signals, prediction outputs, and Adaptive Kalman-ready filtered estimates whenever data is available.
- **FR-019**: Core charts and controls must use labels and must not depend on color alone to communicate status.

### 5.9 Evaluation

- **FR-020**: The system must calculate filter-quality metrics such as variance reduction, residual behavior, and MAE or RMSE when reference data is available.
- **FR-021**: Evaluation outputs must be exportable for the final report or presentation.
- **FR-022**: Results must be reproducible from `../ARX/greenhouse_data.csv` and a saved configuration.

---

## 6. Non-Functional Requirements

### Performance

- **NFR-001**: Prediction plus Adaptive Kalman-ready update should complete within 500 ms per cycle under normal prototype conditions.
- **NFR-002**: Dashboard or output refresh latency should be within 5 seconds under normal conditions.

### Reliability

- **NFR-003**: Prototype uptime during demonstrations and test runs should be at least 95%.
- **NFR-004**: Sensor or replay sample loss should stay below 2% over a long run such as 24 hours.
- **NFR-005**: A single bad measurement must not crash the full pipeline.

### Data Quality and Traceability

- **NFR-006**: A filtered value must be traceable back to its raw measurement, prediction output, timestamp, residual, adaptive status, and configuration context.
- **NFR-007**: Invalid, corrected, interpolated, or skipped samples must be explicitly labeled.

### Maintainability

- **NFR-008**: Prediction, estimator, and future AMPC modules must remain loosely coupled.
- **NFR-009**: Parameters must live in configuration files or settings rather than scattered hard-coded constants.

### Security

- **NFR-010**: Configuration changes must be authorized.
- **NFR-011**: Secrets must not be hard-coded.
- **NFR-012**: Operational endpoints must not be exposed publicly without authentication.

### Browser and Platform Support

- **NFR-013**: The dashboard should work on modern Chrome, Edge, and Firefox.
- **NFR-014**: The development workflow should remain practical on Windows with XAMPP MySQL.
- **NFR-015**: The backend should remain deployable to Linux if needed.
- **NFR-016**: Edge-device integration should remain compatible with ESP32-based nodes.

### Accessibility and Usability

- **NFR-017**: The interface must not rely on color alone to show status.
- **NFR-018**: Core charts and controls must have labels, readable contrast, and a layout suitable for demos and review sessions.

---

## 7. Out of Scope (v1.0)

- Full closed-loop AMPC actuation and unattended receding-horizon control execution.
- Fully autonomous irrigation duration, misting duration, fan scheduling, or closed-loop actuation.
- Deep online adaptation frameworks, broad EKF/UKF/EnKF comparison, or full self-tuning estimation research beyond the minimal Adaptive Kalman mechanism selected in #001.
- Multi-greenhouse, multi-zone, or multi-tenant support.
- Cloud-scale deployment, high-availability clusters, advanced CI/CD, or enterprise production hardening.
- Native Android or iOS apps.
- External weather API, full ET0-based live scheduling, radiation models, or larger physical greenhouse models. FAO-56/ET0 formulas may still be documented for AMPC readiness and offline experiments.
- Automatic online ARX retraining, model registry, or online learning infrastructure. Explicit offline retraining for a selected run is allowed in v1.
- Public-facing marketing website implementation in v1.

---

## 8. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | Which variables are included in Adaptive Kalman estimation first: soil moisture `theta`, root-zone depletion `Dr`, or soil moisture plus temperature and humidity? | Project owner | Open |
| 2 | Is ARX used as a fixed prediction model, a retrained model, an offline-only reference model, or a baseline to compare against LightGBM/XGBoost? | Project owner | Answered: use ARX as an explicit offline retrainable baseline in v1; keep model adapter replaceable; leave LightGBM/XGBoost comparison for later unless explicitly added. |
| 3 | Is `../ARX/greenhouse_data.csv` used for training, tuning, evaluation, or all three? | Project owner | Answered: use it for all three with chronological split; train ARX on train slice, tune/check on validation slice, and reserve test slice for final reported Kalman/ARX evaluation. |
| 4 | Which minimal Adaptive Kalman mechanism is used in v1: bounded innovation-driven `Q`/`R` tuning, another adaptive rule, or an explicitly documented fallback? | Project owner | Open |
| 5 | What initial state, initial covariance, process noise, and measurement noise should be used? | Project owner | Open |
| 6 | Is v1 offline-first, real-time-first, or both from the start? | Project owner | Open |
| 7 | Is mandatory visualization limited to generated plots or a full dashboard? | Project owner | Open |
| 8 | What is the official storage format: MySQL only, CSV export, or both? | Project owner | Open |
| 9 | What threshold counts as good enough Kalman performance beyond the suggested 20-30% variance reduction? | Project owner | Open |
| 10 | Which exact AWS service will host the backend/dashboard later? | Project owner | Open |
| 11 | Does v1 include only AMPC design artifacts/contracts, or also a minimal offline optimizer prototype? | Project owner | Open |
| 12 | Which AMPC state equation is official first: soil-moisture model, FAO-56 root-zone depletion model, or ARX-driven state prediction? | Project owner | Open |

---

## 9. Revision History

| Date | Author | Change Description |
|------|--------|--------------------|
| 2026-04-13 | Project owner / Codex onboarding | Initial v1 technical validation PRD based on `/start` onboarding answers |
| 2026-04-14 | Project owner / Codex | Clarified direction toward Adaptive Kalman + AMPC and added AMPC-ready requirements |
