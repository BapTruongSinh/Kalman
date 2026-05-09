<!--
DOCUMENT METADATA
Owner: @systems-architect
Update trigger: Any significant architectural, technology, or design pattern decision is made
Update scope: Append new ADRs only. Never edit the body of an Accepted ADR.
Read by: All agents. Check this file before proposing changes that may conflict with prior decisions.
-->

# Architecture Decision Records

> This log captures the context and reasoning behind key decisions so they are never lost.
>
> **Rule**: Once an ADR is marked **Accepted**, do not edit its body. If a decision needs to change, write a new ADR that explicitly supersedes the old one.

---

## Decision Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| ADR-001 | Use Vite, Python/Django, MySQL, ARX, and Kalman for v1 state estimation | Accepted | 2026-04-13 |
| ADR-002 | Orient estimation and control contracts toward Adaptive Kalman plus AMPC | Accepted | 2026-04-14 |
| ADR-003 | Lock v1 estimation scope around scalar soil moisture, adaptive R, offline replay, and AMPC-ready docs only | Accepted | 2026-04-14 |
| ADR-004 | Promote online live ingestion with pretrained ARX artifact as the primary runtime path | Accepted | 2026-05-08 |
| ADR-005 | Scope live runs and prediction records by greenhouse | Accepted | 2026-05-09 |
| ADR-006 | Run production AMPC online through Django by greenhouse | Accepted | 2026-05-09 |

---

## ADR-001: Use Vite, Python/Django, MySQL, ARX, and Kalman for v1 state estimation

**Date**: 2026-04-13
**Status**: Accepted
**Deciders**: Project owner / Codex onboarding

### Context

HMPC v1 is a technical validation release, not a full autonomous greenhouse controller. The project already contains `../ARX/`, `../ARX/greenhouse_data.csv`, and a `Kalman/` work area. The primary need is to connect a reliable estimation path: dataset or sensor input, preprocessing, ARX prediction, Kalman update, storage, visualization, and evaluation.

The user selected Vite for frontend, Python for backend, MySQL from XAMPP for database, Django ORM for persistence, npm for frontend package management, and AWS as the eventual deployment target.

### Options Considered

1. **Vite + Python/Django + MySQL + Django ORM**: Fits the selected stack, keeps Python close to ARX/Kalman code, and supports relational experiment logging. Trade-off: Django backend scaffolding still needs to be created or confirmed.
2. **Node/Express + MySQL + custom Python scripts**: Simple JavaScript API path, but separates the web backend from the ARX/Kalman Python logic and adds integration overhead.
3. **Notebook-only Python workflow**: Fast for experimentation, but weak for repeatable storage, dashboard integration, and later deployment.

### Decision

Use Vite for the dashboard, Python/Django for backend services, MySQL from XAMPP with Django ORM for experiment persistence, the existing ARX work as the prediction block, and a standard Kalman pipeline for v1 state estimation.

### Consequences

- **Positive**: Python remains the main modeling environment; Django ORM gives structured storage; Vite keeps the dashboard lightweight; the architecture is extensible toward adaptive estimation and HMPC.
- **Negative**: Exact Django project layout, Python test runner, AWS service, auth approach, and storage/export format still need follow-up decisions.
- **Neutral**: v1 prioritizes local reproducibility and academic evidence over production operations.

---

## ADR-002: Orient estimation and control contracts toward Adaptive Kalman plus AMPC

**Date**: 2026-04-14
**Status**: Accepted
**Deciders**: Project owner / Codex

### Context

After the initial onboarding, the project owner clarified that the real technical direction is not only baseline Kalman plus MPC. The intended topic is Adaptive Kalman plus AMPC for a smart greenhouse. Three research note files were added under `Server/docs/technical/`: `BaoCao.md`, `Tonghop.md`, and `Tonghop2.md`. They emphasize adaptive estimation, Adaptive MPC, FAO-56 water-balance reasoning, AMPC cost and constraints, and prediction-model alternatives such as LightGBM/XGBoost.

ADR-001 still holds for the selected stack and the staged v1 delivery path, but the "standard Kalman only" framing is too narrow for the project direction.

### Options Considered

1. **Keep v1 as standard Kalman plus ARX only**: Simple and low-risk. Cons: likely drifts away from the project owner's intended Adaptive Kalman + AMPC topic and may create module boundaries that are expensive to undo.
2. **Jump directly to full closed-loop AMPC implementation**: Closer to the final topic. Cons: high risk before data quality, estimator behavior, prediction model boundary, and safety constraints are verified.
3. **Keep v1 staged but make it Adaptive Kalman and AMPC-ready**: Preserves the current implementation path while correcting the target architecture and documentation.

### Decision

Use option 3. v1 remains staged around dataset ingestion, preprocessing, prediction, Adaptive Kalman-ready estimation, storage, visualization, and evaluation. ARX remains the first prediction baseline, and it should be retrainable offline for a selected run rather than treated only as a fixed saved artifact. Prediction must remain replaceable or comparable later with LightGBM/XGBoost. Estimator tasks must resolve a minimal Adaptive Kalman mechanism rather than treating adaptation as irrelevant. AMPC state, control, disturbance, cost, and safety contracts must be documented before controller implementation.

### Consequences

- **Positive**: The project now aligns with the owner's clarified topic; future AMPC work is less likely to require redesign; the final report can cite a coherent path from data to estimator to control design.
- **Positive**: Explicit offline ARX retraining lets the project demonstrate a reproducible prediction baseline while keeping online retraining/model registry out of v1.
- **Negative**: Task #001 becomes more important because it must choose a bounded adaptive-estimation rule and decide whether v1 includes an offline AMPC optimizer prototype.
- **Neutral**: Full autonomous actuation remains gated until requirements explicitly promote it.

---

## ADR-003: Lock v1 estimation scope around scalar soil moisture, adaptive R, offline replay, and AMPC-ready docs only

**Date**: 2026-04-14
**Status**: Accepted
**Deciders**: Project owner / Codex

### Context

ADR-002 intentionally left several v1 implementation details open so task `#001` could resolve them with owner input. The owner has now answered the estimator-target, data-flow, adaptive-rule, initialization, storage, and AMPC-boundary questions. Those answers are concrete enough that downstream tasks `#002` through `#005` and `#013` should no longer stay blocked on ambiguity.

The main remaining risk is accidental re-expansion of scope. Without a precise ADR, implementation could drift toward multi-state estimation, adaptive `Q` plus `R`, live-first ingestion, or an early AMPC optimizer prototype before the estimation path is validated.

### Options Considered

1. **Keep decisions only in task notes and PRD text**: Lightweight, but downstream implementation can still reinterpret the architecture and re-open already settled choices.
2. **Lock the resolved v1 boundary in a dedicated ADR**: Adds one more decision record, but gives downstream tasks a stable architectural contract.
3. **Promote scope directly to multi-state estimation plus offline AMPC prototype**: More ambitious, but increases implementation and debugging risk before the replay estimator is stable.

### Decision

Use option 2. For v1:

- The first estimator state is scalar `Soil_Moisture`.
- ARX remains the explicit offline retrainable baseline prediction block.
- Data flows from a time-series table/query result with chronological split (`train 60% / validation 20% / test 20%`); CSV is treated as a snapshot/export of that table, not the permanent hard-coded storage model.
- The minimal adaptive mechanism is bounded innovation-driven adaptive `R`; `Q` remains fixed during a run and is tuned on validation.
- Default initialization is `x0 = first observed Soil_Moisture`, `P0 = 1.0`, `Q = 0.05` unless validation selects another value, `R0 = 1.0`, `R_min = 0.05`, `R_max = 25.0`, `alpha = 0.95`.
- v1 is offline-first for replay and evaluation. Live ingestion is a later extension, not the primary delivery path.
- MySQL from XAMPP is the local source of truth for persistent storage; CSV remains a replay/export format.
- v1 includes AMPC-ready state/control/disturbance/cost/safety contracts only. It explicitly excludes an AMPC optimizer prototype and closed-loop actuation.
- The held-out test acceptance gate is: full replay completes without crash, each output row logs timestamp/raw/predicted/filtered/innovation/`P`/`R`/status, innovation and covariance remain bounded without sustained explosion or long saturation, first-difference variance reduction passes at `>= 20%` with `>= 30%` as target, and filtered RMSE/MAE do not degrade more than 5% versus ARX prediction.

### Consequences

- **Positive**: Downstream implementation can proceed without reopening the estimator shape or AMPC boundary.
- **Positive**: v1 now has a clear academic narrative: retrainable ARX baseline -> adaptive scalar estimator -> held-out evaluation -> AMPC-ready contracts.
- **Negative**: Multi-state estimation and adaptive `Q` remain postponed even if future experiments might benefit from them.
- **Neutral**: AWS hosting selection still remains deferred because it does not affect the local estimation path.

---

## ADR-004: Promote online live ingestion with pretrained ARX artifact as the primary runtime path

**Date**: 2026-05-08
**Status**: Accepted
**Supersedes**: ADR-003 runtime/data-flow parts for new application runtime work. ADR-003 remains valid for scalar soil moisture, adaptive `R`, AMPC docs-only scope, and evaluation guardrails.
**Deciders**: Project owner / Codex

### Context

The project owner requested cleanup toward a single online runtime: live sensor ingestion should use the existing `../ARX/arx_model.json` artifact for prediction and should not train a new ARX model inside the application request path. The existing implementation already had a secure live endpoint, but it intentionally passed `adapter=None`, so Kalman priors fell back to the previous posterior. At the same time, older docs and helper APIs still described offline replay plus app-side ARX retraining as the main path.

### Options Considered

1. **Keep offline replay/retraining as the main runtime**: Preserves old tests and docs, but conflicts with the requested online artifact-only direction.
2. **Switch live ingestion to artifact-only ARX and keep offline utilities as non-runtime research/test helpers**: Aligns the app runtime with the owner request while avoiding destructive schema/test churn.
3. **Delete offline enums, split helpers, replay helpers, and ARX training utilities now**: Cleans the application around the real owner target: online ingest with a fixed server-side ARX artifact.

### Decision

Use option 3. The primary application runtime is `POST /api/ingest/samples/`: authenticate the device user, validate/preprocess one live sample, load a cached `ARXPredictionAdapter` from `settings.ARX_MODEL_PATH` (default `../ARX/arx_model.json`), reconstruct the minimal per-run live history from persisted `PipelineCycle` rows, pass the adapter into `AdaptiveKalmanCycle`, and persist `arx_predicted` plus Kalman outputs. If the artifact is missing or invalid, live ingestion continues with carry-forward prior and logs the internal warning; no request payload can override the model path.

Offline replay, chronological split, app-side ARX OLS training, native adapter artifact saving, replay source enums, and split-ratio config are removed from the application code and tests. Existing database rows are normalized to the live-only vocabulary by migration `0006_live_only_cleanup`; derived evaluation summaries are deleted and can be recomputed as the single `online` summary.

### Consequences

- **Positive**: Live ingestion now uses the pretrained ARX prior when enough per-run history exists.
- **Positive**: Runtime no longer needs app-side ARX training or user-supplied model paths.
- **Positive**: Schema and code are live-only: `run_type='live'`, `source_type='live'`, `slice_type='online'`, no `ARXArtifact` table, no split-ratio fields, no `AdaptiveKalmanCycle.replay()`.
- **Positive**: Security boundary remains intact: token auth, greenhouse owner checks, run status guard, and server-side artifact path.
- **Negative**: Historical `EvaluationSummary` rows are derived data and are dropped during migration to avoid train/validation/test collision; recompute online metrics after migration if needed.

---

## ADR-005: Scope live runs and prediction records by greenhouse

**Date**: 2026-05-09
**Status**: Accepted
**Deciders**: Project owner / Codex

### Context

The project is moving toward an online product where multiple users can use the system, and one user can monitor multiple greenhouses. Sensor samples are stored first, then the estimator/controller reads the persisted state for the correct greenhouse. Storing both `user_id` and `greenhouse_id` on prediction records would duplicate ownership and risk drift.

### Options Considered

1. **Store `user_id` directly on every prediction/run row**: Easy to filter, but duplicates the same ownership data and can become inconsistent when greenhouse ownership changes.
2. **Store only `greenhouse_id` on live runs and prediction cycles**: Keeps the runtime query explicit while deriving the user through `Greenhouse.owner`.
3. **Keep the existing `ExperimentRun.owner` field only**: Works for one greenhouse per user, but cannot distinguish multiple greenhouses owned by the same account.

### Decision

Use option 2. Add `greenhouses(owner_id, name, is_active, ...)`, move `ExperimentRun` to `greenhouse_id`, and denormalize `PipelineCycle.greenhouse_id` for fast latest-state lookups. Live ingest authorization checks `ExperimentRun.greenhouse.owner_id` and blocks inactive greenhouses. Existing rows are migrated into a default greenhouse per previous run owner; rows without an owner use an inactive legacy user.

### Consequences

- **Positive**: AMPC/Kalman online execution can read latest state by greenhouse without accepting `state-json` from users.
- **Positive**: Prediction records do not duplicate `user_id`; ownership has one source of truth.
- **Positive**: Dashboard run lists can be scoped to the authenticated user's greenhouses and filtered by `greenhouse_id`.
- **Negative**: Migration is schema-destructive for the old `ExperimentRun.owner` column; rollback recreates the column but cannot restore per-run owner assignments except through greenhouse ownership.

---

## ADR-006: Run production AMPC online through Django by greenhouse

**Date**: 2026-05-09
**Status**: Accepted
**Supersedes**: ADR-003 "AMPC docs-only" boundary for the production controller integration path. ADR-003 still describes the original estimation-first v1 methodology and evaluation gates.
**Deciders**: Project owner / Codex

### Context

The project now has a separate `MPC/` package with deterministic MPC and AMPC bias-correction code. The production web path must not ask users to upload `state-json`, model paths, input CSVs, or CLI arguments. It must read the latest validated Kalman state/history from MySQL, scope everything by `greenhouse_id`, and optionally dispatch a safe pump command only when a greenhouse actuator profile is explicitly enabled and valid.

### Options Considered

1. **Keep AMPC as CLI-only**: Low integration risk, but the dashboard cannot run controller decisions from real stored Kalman state.
2. **Expose user-supplied model/state paths through Django**: Flexible, but violates the server-side artifact and IDOR/security boundary.
3. **Add a Django service/API around server-side ARX, DB state, greenhouse profiles, and AMPC audit rows**: More schema/API work, but matches production ownership, auditability, and fail-closed safety requirements.

### Decision

Use option 3. Add per-greenhouse `GreenhouseControlProfile` and `AMPCRecommendation` tables. The Django service verifies `Greenhouse.owner` before reading state, loads `settings.ARX_MODEL_PATH`, builds AMPC state/history from persisted `PipelineCycle` rows, applies bias correction from recent Kalman/ARX residuals, solves with the `MPC/` package, persists every recommendation/audit snapshot, and returns dashboard JSON. Actuator execution is optional, defaults off, uses Bearer token env vars only, rejects unsafe URLs, and fail-closes to pump `0` on state/model/solver/config/HTTP errors.

### Consequences

- **Positive**: The web product can run AMPC per greenhouse without CLI or user-supplied model/state files.
- **Positive**: Multi-user authorization, state provenance, controller config, predicted horizon, cost, safety status, and actuator results are auditable in MySQL.
- **Positive**: The AMPC path reuses the existing Kalman live state and `MPC/` package instead of duplicating controller math in Django.
- **Negative**: Backend deployments must install the sibling `greenhouse-mpc` package or internal wheel; missing dependency breaks AMPC imports.
- **Neutral**: Real hardware actuation remains gated by explicit greenhouse profile config and environment secrets; default behavior is recommendation-only.

---

<!--
TEMPLATE FOR NEW ADRs - copy this block when adding a new record:

## ADR-[NNN]: [Short Title]

**Date**: YYYY-MM-DD
**Status**: Accepted
**Deciders**: [Human name(s)] / @systems-architect

### Context
[What situation or problem prompted this decision. Include relevant constraints.]

### Options Considered
1. **[Option A]**: [Description] - Pros: [...] Cons: [...]
2. **[Option B]**: [Description] - Pros: [...] Cons: [...]

### Decision
[What was decided and the primary reason why.]

### Consequences
- **Positive**: [What becomes easier or better]
- **Negative**: [Trade-offs or what becomes harder]
- **Neutral**: [What changes but is neither better nor worse]
-->
