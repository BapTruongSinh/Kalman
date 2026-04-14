# Phase 1 Onboarding Answers

> Update 2026-04-14: Project owner clarified that the correct technical direction is Adaptive Kalman + AMPC, not only baseline Kalman + MPC. The original Phase 1 answers below are preserved as historical onboarding notes; use `PRD.md`, `DECISIONS.md` ADR-002, and `ADAPTIVE_KALMAN_AMPC_NOTES.md` for the current direction.

> File này lưu lại câu trả lời gốc từ Phase 1 của `.claude/START_HERE.md`.
> Mục đích là giữ một bản Q/A rõ ràng để agent không phải suy luận lại từ `PRD.md`, `README.md`, hoặc review memory.

---

## Group 1 - Project Basics

### 1. What is the name of this project?

HMPC.

### 2. What does it do in one sentence?

It is a smart greenhouse system that uses real-time sensor data, Adaptive Kalman filtering, and HMPC to predict environmental changes and automatically optimize irrigation, misting, and ventilation.

### 3. Who are the primary users?

The project owner / developer.

### 4. What problem does it solve?

It solves inefficient and reactive greenhouse control in environments where soil moisture, temperature, and humidity change continuously and affect one another. Without this system, users usually rely on manual observation, separate sensor readings, and simple threshold-based actions, which can be slow, inconsistent, and unable to predict future changes.

---

## Group 2 - Tech Stack

### 5. What is the frontend technology?

Vite.

### 6. What is the backend?

Python. Django is assumed because the selected query layer is Django ORM.

### 7. What database?

MySQL from XAMPP.

### 8. What ORM or query layer?

Django ORM.

### 9. What is the hosting/deployment target?

AWS.

### 10. What package manager?

npm.

### 11. What Node version?

Latest version, not pinned yet.

---

## Group 3 - Conventions

### 12. What formatter and linter?

Prettier + ESLint.

### 13. What test runner for unit tests?

Vitest.

### 14. What are the dev / build / test commands?

- `npm run dev`
- `npm run build`
- `npm test`
- `npm start`

---

## Group 4 - Product Requirements

### 15. What are the main features this product must have in v1?

v1 is intentionally limited to a reliable state-estimation pipeline:

`Sensor / Dataset -> Preprocess -> ARX Predict -> Kalman Update -> Store -> Visualize -> Evaluate`

Main v1 features:

- Ingest live sensor data and offline data from `../ARX/greenhouse_data.csv`.
- Validate and preprocess missing, malformed, out-of-range, and repeated samples.
- Reuse the existing ARX work as the prediction block for Kalman.
- Run a complete Kalman cycle for each time step.
- Compare raw, ARX predicted, and Kalman filtered signals.
- Store raw measurements, ARX outputs, Kalman estimates, residuals, timestamps, and pipeline logs.
- Preserve experiment configuration for reproducibility.
- Produce evaluation metrics such as variance reduction, residual behavior, MAE, and RMSE when reference data is available.

### 16. Are there any non-functional requirements?

Key NFR targets:

- ARX + Kalman cycle latency: `<= 500 ms`.
- Dashboard refresh latency: `<= 5 s`.
- Prototype uptime during testing: `>= 95%`.
- Sensor sample loss per day: `< 2%`.
- Configuration access: authorized users only.
- Data traceability: raw, ARX, and Kalman outputs stored separately or clearly labeled.
- Dashboard support: modern Chrome, Edge, and Firefox.
- Local development: practical on Windows with XAMPP MySQL.
- Backend deployability: Linux-compatible if needed.
- Edge-device compatibility: ESP32-based nodes.
- Accessibility: status must not depend on color alone; charts and controls need labels and readable contrast.

### 17. What is explicitly out of scope for v1?

Out of scope for v1:

- HMPC and full optimal control.
- Fully autonomous irrigation, misting, and fan scheduling.
- Advanced adaptive Kalman variants, EKF/UKF comparison, or self-tuning estimation frameworks.
- Multi-greenhouse, multi-zone, or multi-tenant support.
- Cloud-scale deployment and enterprise operations.
- Native mobile apps.
- External weather, ET0, radiation models, or advanced physical greenhouse models.
- Automatic ARX retraining, model registry, or online learning infrastructure.

### 18. Who is the product owner / decision maker?

The project owner / user.

---

## Group 5 - Content & SEO

### 19. Does the product have public-facing pages?

Yes, but not in v1.

### 20. Do you have a defined brand voice or tone?

Not yet.

### 21. Are there SEO goals?

Not yet.

### 22. Do you already have copy for any pages?

Not yet.

---

## Group 6 - Goals and Open Questions

### 23. What does success look like?

Success in v1 means the system can reliably estimate greenhouse states using Kalman Filter, with the ARX model serving as the prediction model and `../ARX/greenhouse_data.csv` used for development, testing, and evaluation.

Success is not full autonomous greenhouse control. It means this pipeline works correctly and consistently:

`data input -> ARX prediction -> Kalman update -> storage -> visualization -> evaluation`

Suggested success metrics:

- Pipeline execution success rate: at least `95%`.
- Estimation latency per cycle: `<= 500 ms`.
- Dashboard or output update delay: `<= 5 s`.
- Sample loss rate: `< 2%` over a long test such as 24 hours.
- Variance reduction: at least `20-30%` compared with raw sensor data.
- Residual behavior: stable and not persistently exploding.
- Visualization: raw, predicted, and filtered curves stored and viewable.
- Logging completeness: raw measurement, ARX prediction, Kalman filtered state, timestamp, and residual for each cycle.
- Robustness: no full system crash under short-term missing or noisy data.
- Reproducibility: results regenerate consistently from the dataset and saved configuration.

### 24. Are there any open decisions not yet made?

Open decisions:

- Which variables are included in Kalman estimation first: soil moisture only, or soil moisture plus temperature and humidity?
- How exactly ARX is used: fixed prediction model, retrained model, or offline-only reference model.
- How `../ARX/greenhouse_data.csv` is used: training, tuning, evaluation, or all three.
- Which Kalman variant v1 uses: standard Kalman Filter only, or a limited adaptive extension.
- What initial Kalman parameters are used: initial state, initial covariance, process noise, and measurement noise.
- Whether v1 is offline-first, real-time-first, or both.
- What visualization is mandatory: logs, plots, or a full dashboard.
- What storage format is official: CSV, relational database, time-series database, or combined approach.
- What counts as good enough Kalman performance.
- What is explicitly postponed to v2.
