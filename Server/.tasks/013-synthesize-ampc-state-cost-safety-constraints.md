---
id: "013"
title: "Synthesize AMPC state, cost, and safety constraints"
status: "completed"
area: "docs"
agent: "@systems-architect"
required_skill: "software-architecture"
supporting_skills: ["statsmodels", "scientific-writing"]
priority: "normal"
created_at: "2026-04-14"
due_date: null
started_at: "2026-04-15"
completed_at: "2026-04-15"
prd_refs: ["FR-025", "FR-026", "FR-027"]
blocks: ["012"]
blocked_by: ["001"]
---

## Description

Turn the AMPC material from `BaoCao.md`, `Tonghop.md`, `Tonghop2.md`, and `docs/technical/ADAPTIVE_KALMAN_AMPC_NOTES.md` into a concise implementation-ready modeling note. The output must define the first candidate state, actuator inputs, disturbances, cost terms, constraints, and fallback rules used to connect Adaptive Kalman estimates to later AMPC work.

## Acceptance Criteria

- [x] Candidate state choice is documented, including `theta` soil moisture and/or `Dr` root-zone depletion.
- [x] Candidate control inputs are documented, including drip/pump seconds, mist seconds, and fan duration or level when available.
- [x] Candidate disturbances are documented, including ET0/ETc if used, temperature, humidity, and light.
- [x] Cost terms are documented: zone/range tracking, water/energy penalty, actuator switching penalty, and `Delta u` smoothing.
- [x] Safety constraints and fallbacks are documented: soil moisture bounds, RH max, daily water cap, no mist at high RH/night, emergency fallback, and sensor-fault fallback.
- [x] The note states whether v1 implements only AMPC contracts or also a minimal offline optimizer prototype.
- [x] Relevant documentation updated.

## Technical Notes

Use this as the practical AMPC handoff task, not as a request to implement full autonomous actuation immediately. The starter equation from the research notes is `Dr,k+1 = Dr,k + ETc,k - (eta Q / A) u_k`, with `u_k` as pump/drip seconds.

**Deliverable**: `docs/technical/AMPC_MODELING_HANDOFF.md` plus cross-links from `ARCHITECTURE.md`, `METHODOLOGY_V1.md`, `DATABASE.md`, `CLAUDE.md`, `USER_GUIDE.md`.

## History

| Date | Agent / Human | Event |
|------|---------------|-------|
| 2026-04-14 | Codex | Task created after user clarified the project target as Adaptive Kalman + AMPC |
| 2026-04-15 | Cursor | Completed: added `AMPC_MODELING_HANDOFF.md`; synced cross-docs, TODO, FR traceability; v1 scope explicitly **contracts only** (no offline AMPC optimiser in shipped code). |
