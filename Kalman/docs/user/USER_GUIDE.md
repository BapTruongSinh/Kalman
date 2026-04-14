<!--
DOCUMENT METADATA
Owner: @documentation-writer
Update trigger: Any user-facing workflow is added, changed, or removed
Read by: @qa-engineer
-->

# Adaptive Kalman + AMPC User Guide

> Last updated: 2026-04-14
> Version: 0.2.0

---

## Status

The v1 user workflow is not implemented yet. This guide records the intended demo and replay flow so future implementation can keep documentation synchronized.

---

## Intended v1 Workflow

1. Load greenhouse data from `../ARX/greenhouse_data.csv`.
2. Validate and preprocess the input samples.
3. Run prediction for each selected time step; ARX is the initial baseline model.
4. Run the Adaptive Kalman-ready estimator update using the prediction output and real measurement.
5. Store raw measurement, prediction output, filtered estimate, residual/innovation, adaptive status, timestamp, status, and configuration context.
6. View or export raw, predicted, and filtered curves.
7. Generate evaluation metrics for reporting.
8. Use the documented AMPC state/control/disturbance/cost/safety contract as the bridge to later controller work.

---

## Expected Demo Evidence

- Raw sensor signal compared with prediction output and Adaptive Kalman-ready filtered estimate.
- Cycle success rate of at least 95% for valid samples.
- Prediction plus estimator cycle latency at or below 500 ms under prototype conditions.
- Dashboard or output refresh delay at or below 5 seconds.
- Sample loss below 2% over a long run such as 24 hours.
- 20-30% variance reduction compared with raw signal where appropriate.
- Residuals remain bounded and do not show persistent exploding behavior.
- Adaptive estimator status is explainable when adaptive behavior is enabled.
- AMPC readiness is documented through state, control input, disturbance, cost, and safety definitions.
- Results can be regenerated from `../ARX/greenhouse_data.csv` and saved configuration.

---

## Common Issues

### Dataset path is missing

Confirm that `../ARX/greenhouse_data.csv` exists and has not been moved.

### Results cannot be reproduced

Confirm that the run configuration was saved with the experiment and that the same dataset version is being used.

### Filter output looks too smooth or too noisy

Review the estimator parameters, prediction behavior, residual/innovation plots, adaptive status, and preprocessing status labels. The final Adaptive Kalman tuning strategy is still an open v1 decision.
