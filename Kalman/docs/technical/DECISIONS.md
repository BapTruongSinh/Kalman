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

After the initial onboarding, the project owner clarified that the real technical direction is not only baseline Kalman plus MPC. The intended topic is Adaptive Kalman plus AMPC for a smart greenhouse. Three research note files were added under `Kalman/docs/technical/`: `BaoCao.md`, `Tonghop.md`, and `Tonghop2.md`. They emphasize adaptive estimation, Adaptive MPC, FAO-56 water-balance reasoning, AMPC cost and constraints, and prediction-model alternatives such as LightGBM/XGBoost.

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
