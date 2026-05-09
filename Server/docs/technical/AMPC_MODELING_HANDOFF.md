<!--
DOCUMENT METADATA
Owner: @systems-architect
Update trigger: AMPC state/control/cost/safety contract changes or v2 controller kickoff
Read by: Anyone implementing MPC beyond v1 estimation
-->

# AMPC Modeling Handoff — State, Cost, and Safety (v1 → v2)

> Last updated: 2026-04-15
> Version: 1.0.0
> Task: #013
> Normative product refs: **FR-025**, **FR-026**, **FR-027** (`PRD.md`)

This note is the **implementation-ready synthesis** of AMPC-oriented material from:

- [`BaoCao.md`](./BaoCao.md) — academic framing (MPC/HMPC, Kalman, FAO-56, costs, constraints, evaluation metrics).
- [`Tonghop.md`](./Tonghop.md) — MPC loop, measured vs unmeasured disturbances, zone costs, adaptive MPC motivation.
- [`Tonghop2.md`](./Tonghop2.md) — dataset/actuator causality, ARX structure, `Dr` vs soil moisture, control as pump/drip seconds, ET0/ETc, starter water-balance equation.
- [`ADAPTIVE_KALMAN_AMPC_NOTES.md`](./ADAPTIVE_KALMAN_AMPC_NOTES.md) — project-local research summary and backlog hooks.

Frozen v1 decisions remain in [`DECISIONS.md`](./DECISIONS.md) and [`ARCHITECTURE.md`](./ARCHITECTURE.md) § AMPC-Ready Modeling Boundary. This document **narrows symbols, interfaces, and fallbacks** so a future controller task does not reinterpret the greenhouse CSV or Kalman logs ad hoc.

---

## 1. v1 scope boundary (normative)

| Statement | Meaning |
|-----------|---------|
| **Contracts only in v1** | The repository ships **documentation + estimation + evaluation**; there is **no** receding-horizon optimiser (QP/NLP), **no** closed-loop actuator scheduler, and **no** minimal “offline AMPC prototype” solver in production code paths. |
| **FR-027** | Interfaces (`PredictionAdapter`, `CycleResult` → `PipelineCycle`, evaluation exports) must stay **replaceable**; AMPC must not assume a fixed ARX internal representation. |
| **What v1 already provides** | Time-aligned traces of **Drip / Mist / Fan**, **Temperature / Humidity / Light**, **Soil_Moisture**, plus Kalman outputs (`kf_x_*`, innovations, adaptive `R`, covariances, statuses). |

---

## 2. Candidate state (FR-025)

### 2.1 Primary scalar state θ (soil moisture)

- **Definition**: θ\_k is **root-zone soil moisture** on the same physical scale as the dataset column `Soil_Moisture` and v1 Kalman channels (`raw_soil_moisture`, `kf_x_posterior`, etc.).
- **v1 role**: θ is the **first locked estimation target** (ADR-002 / task #001). Adaptive Kalman v1 produces a filtered θ̂\_k trace suitable as the **measured/controlled output** for a later output-feedback MPC formulation.
- **Measurement**: use the **preprocessed** measurement fed to the Kalman update (same convention as `CycleResult` / `PipelineCycle`) so MPC and estimation share one definition of “z\_k”.

### 2.2 AMPC-oriented root-zone depletion D\_r

- **Definition** (FAO-56 style): D\_r,k ∈ [0, TAW] is **readily available root-zone water depletion** (mm water equivalent), complementary to θ when soil-column parameters exist.
- **Starter discrete balance** (from research notes; symbols explicit):

\[
D_{r,k+1} = D_{r,k} + ET_{c,k} - \frac{\eta\,Q}{A}\, u_{\text{drip},k}
\]

| Symbol | Meaning | v1 dataset |
|--------|---------|------------|
| \(ET_{c,k}\) | Crop evapotranspiration increment over the control interval | **Not** in `greenhouse_data.csv` — treat as **external disturbance feed** (weather + Kc) in v2+. |
| \(u_{\text{drip},k}\) | Drip / pump command mapped to water depth equivalent | Use `Drip` column as **proxy command variable** until hardware calibration exists. |
| \(\eta Q / A\) | Efficiency × nominal flow / representative area | **Calibration constant** — not identifiable from moisture CSV alone. |

- **θ ↔ D\_r conversion** (documentation only until parameters are known):

\[
TAW = 1000\,(\theta_{FC}-\theta_{WP})\,Z_r,\quad
D_r = 1000\,(\theta_{FC}-\theta)\,Z_r,\quad
\theta = \theta_{FC} - \frac{D_r}{1000\,Z_r}
\]

\(\theta_{FC}\), \(\theta_{WP}\), \(Z_r\) are **soil–crop parameters**, not columns in the current CSV.

**Handoff choice**: implement MPC **first** on θ with zone tracking using θ̂ from Kalman; add **parallel D\_r dynamics** once ET\_c and soil parameters are available, without breaking the θ interface.

---

## 3. Candidate control inputs u (FR-025)

Vector **u\_k = [ u\_drip, u\_mist, u\_fan ]^T** aligned with CSV actuators:

| Channel | CSV column | Candidate physical meaning | v1 usage |
|---------|------------|------------------------------|----------|
| Drip | `Drip` | Pump / drip **on-time or command intensity** per sampling interval (e.g. seconds per minute) | Logged **traceability**; not optimised |
| Mist | `Mist` | Mist **on-time** or duty | Idem |
| Fan | `Fan` | Fan **on-time**, speed, or discrete level encoded numerically | Idem |

**Rate / dwell constraints** (from `Tonghop2.md` “minimum switching time”): enforce minimum on/off duration and slew limits in MPC as **hard or softened** inequalities on Δu and binary dwell — prevents chattering solutions incompatible with pumps/valves.

---

## 4. Disturbances and measured outputs (FR-025)

### 4.1 Measured exogenous signals (available now)

Use as **d\_k** entries for disturbance-aware prediction and offset MPC:

- `Temperature`, `Humidity`, `Light` (and any future exogenous columns added with migrations).

### 4.2 Water-balance disturbances (planned)

- **ET0** (reference crop evapotranspiration) and **ETc = Kc · ET0** drive D\_r open-loop dynamics.
- **v1**: document as **forward inputs** to the handoff model; **do not** silently invent ET series from moisture alone.

### 4.3 Unmeasured disturbances

Wind gusts, leaks, model error — per `Tonghop.md`, treat via **disturbance observer / inflated bounds / terminal penalty**, outside v1 code.

---

## 5. Candidate cost terms J (FR-026)

Multi-objective stage cost (conceptual; weights are design parameters):

\[
J = \sum_{i=1}^{P} \Big(
\underbrace{\phi_{\text{zone}}(\hat\theta_{k+i})}_{\text{soil moisture band}}
+ \underbrace{\lambda_w\, \psi_w(u_{k+i})}_{\text{water use}}
+ \underbrace{\lambda_e\, \psi_e(u_{k+i})}_{\text{energy / fan}}
+ \underbrace{\lambda_{sw}\,\psi_{sw}(u_{k+i},u_{k+i-1})}_{\text{actuator switching}}
+ \underbrace{\|u_{k+i}-u_{k+i-1}\|^2_{W}}_{\Delta u \text{ smoothing}}
\Big)
\]

| Term | Intent | Notes |
|------|--------|-------|
| φ\_zone | Prefer θ inside **[Soil\_Low\_SP, Soil\_High\_SP]**-style band | Use **soft** penalties (slack) before hard output constraints to avoid infeasibility on dry spells |
| ψ\_w | Penalise drip+mist water | Tie to calibrated u→volume map later |
| ψ\_e | Penalise aggressive fan / pump energy | Proxy via duty cycle until power meters exist |
| ψ\_sw | Penalise frequent toggles | Surrogate: L2 on Δu plus explicit min-dwell (§3) and logic rows (§6) |
| Δu smoothing | ‖Δu‖² | Standard MPC regularisation; aligns with HMPC discussion in `BaoCao.md` |

---

## 6. Safety constraints and fallbacks (FR-026)

| ID | Class | Rule | Source intuition |
|----|-------|------|-------------------|
| **S-θ** | hard/soft | θ\_min ≤ θ ≤ θ\_max | Absolute soil moisture guardrails |
| **S-RH** | hard/soft | RH ≤ RH\_max | `Humidity` channel; tie to mist permission |
| **S-water** | hard | ∑\_day water(u) ≤ cap | Daily water budget |
| **S-mist** | logic | **No mist** when RH high **or** night window | Operator + `Light`/clock policy |
| **S-fan** | hard | u\_fan within safe duty | Mechanical limit |
| **F-emerg** | **emergency** | If θ < θ\_emerg → apply **max legal** irrigation once, bypass economy | From `BaoCao.md` emergency narrative |
| **F-sensor** | **sensor fault** | If estimator flags `cycle_status ∈ {error, skipped_invalid}` or repeated invalid measurements → **hold u**, switch to **open-loop** schedule, **inflate uncertainty** / skip MPC update | Bridges to v1 `PipelineCycle` statuses and `kf_P` |

---

## 7. Connection to Adaptive Kalman estimates (interface contract)

| Kalman artefact | MPC use (v2+) |
|-----------------|---------------|
| θ̂\_k (`kf_x_posterior` or agreed measurement map) | Output / tracking feedback |
| P̂\_k (`kf_P_posterior`) | Tube / chance constraint sizing, less aggressive u when uncertain |
| Innovation e\_k, adaptive R\_k | Fault detection hooks; trigger **F-sensor** |
| `cycle_status`, `preprocess_status`, `error_message` | **Gating**: do not optimise against known-bad samples |

---

## 8. Suggested implementation sequencing (non-normative)

1. Calibrate θ\_FC, θ\_WP, Z\_r **or** fit a shallow surrogate θ-dynamics model with identifiable parameters from logged u and weather.
2. Add ET0/ETc feed (batch or API) and validate against water balance residuals.
3. Build **LTV / adaptive linear** prediction model for MPC around operating points informed by replay data.
4. Add **QP/NLP** controller in a **separate service** behind the same `PredictionAdapter`-style boundary (FR-027).
5. Hardware-in-the-loop tests; promote soft constraints where field trials show infeasibility.

---

## 9. Traceability (FR mapping)

| FR | Covered in |
|----|--------------|
| **FR-025** | §§2–4 (state, control, disturbances) |
| **FR-026** | §§5–6 (cost + safety/fallback) |
| **FR-027** | §1 + §8 (no early hardwiring; sequencing keeps estimator/controller decoupled) |

---

## 10. Further reading

| Document | Role |
|----------|------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | System decomposition, `PipelineCycle` mapping |
| [`METHODOLOGY_V1.md`](./METHODOLOGY_V1.md) | Scientific narrative + v1 evaluation story |
| [`DECISIONS.md`](./DECISIONS.md) | ADR-002 AMPC boundary |
| [`DATABASE.md`](./DATABASE.md) | Where AMPC-derived columns would land once migrated |
