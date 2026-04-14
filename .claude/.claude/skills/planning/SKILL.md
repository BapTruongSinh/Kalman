---
name: planning
description: >
  Use when managing the project backlog, planning sprints, decomposing features into tasks,
  making architecture decisions, writing ADRs, or designing system components. Provides
  frameworks for both project management and technical architecture.
---

## Backlog Prioritisation — ICE Scoring

Use ICE scoring when recommending task order or comparing competing backlog items:

- **Impact** (1–10): how much does completing this task move a key metric or unblock other work?
- **Confidence** (1–10): how certain are we that completing this achieves the stated impact?
- **Effort** (1–10, inverted): how complex is the work? (10 = trivial, 1 = enormous)

**ICE score = (Impact × Confidence) ÷ Effort**

Present scores transparently alongside your reasoning so the human can override with context you do not have. ICE is a reasoning tool, not a dictator.

---

## Dependency Graph Thinking

Before sequencing any set of tasks, map the dependency graph:

1. List all tasks involved.
2. Mark which tasks **block** others — a blocker must be complete before the blocked task can start.
3. Identify the **critical path**: the longest chain of dependent tasks. This sets the minimum delivery timeline and cannot be compressed without parallelism.
4. Identify **parallel opportunities**: tasks with no dependency on each other that can run simultaneously.
5. Flag parallel tasks explicitly: "These two tasks can run concurrently — consider assigning them in parallel."

Always populate `blocks:` and `blocked_by:` in task files before implementation begins.

---

## Risk Identification and Spike Tasks

For each planned feature, identify the highest-risk assumption and surface it before work begins:

- **Technical risk**: "We assume the third-party API supports batch operations — verify this before building the UI."
- **Requirements risk**: "FR-007 says 'real-time updates' but does not define latency — clarify before designing the architecture."
- **Dependency risk**: "This feature requires the schema to be complete before the API layer can start."

When an assumption is high-risk, propose a **spike task**: a time-boxed investigation with a fixed output (e.g., "Prototype batch API call and confirm rate limits — 2h timebox, output: go/no-go decision"). Spikes de-risk before committing to full implementation.

---

## Definition of Done

A task is only complete when ALL of the following are true:

- [ ] Implementation is complete and merged
- [ ] Tests are written and passing (unit + integration/E2E as appropriate)
- [ ] Relevant documentation is updated
- [ ] PR has been reviewed and approved
- [ ] Deployed to staging (or the appropriate environment for the project)

Use this as the merge gate. Do not move a task to "Completed" if any item is outstanding.

---

## Sprint Health Signals

Proactively flag these patterns when you observe them:

- **WIP creep**: more than 2 items "In Progress" simultaneously — focus is lost; finish before starting new work.
- **Stale WIP**: a task has been "In Progress" for more than 1 week without a history update — investigate the blocker.
- **Blocked task accumulation**: multiple tasks blocked by the same dependency — escalate to resolve the bottleneck.
- **Backlog growth without completion**: new tasks are added faster than old ones close — flag the imbalance explicitly.

---

## Scope Creep Detection

Every request that is not traceable to a requirement in `PRD.md` is potential scope creep. When you identify it:

1. Name it explicitly: "This request is not in the current PRD scope."
2. Estimate the impact: "Adding this adds approximately X tasks and delays Y by Z."
3. Ask the human to decide: add to backlog, defer to a future milestone, or update the PRD.

Do not silently add out-of-scope tasks to the backlog.

---

## Task File Format

Every TODO.md item has a corresponding file in `.tasks/` named `NNN-short-title.md`. Copy `.tasks/TASK_TEMPLATE.md` as the starting point for every new task file. Use this exact structure:

```
---
id: "NNN"
title: "..."
status: "todo | in_progress | completed | blocked"
area: "..."
agent: "@agent-name"
priority: "high | normal | low"
created_at: "YYYY-MM-DD"
due_date: null or "YYYY-MM-DD"
started_at: null or "YYYY-MM-DD"
completed_at: null or "YYYY-MM-DD"
prd_refs: ["FR-001"]
blocks: ["005"]
blocked_by: ["002"]
---
## Description
## Acceptance Criteria
## Technical Notes
## History
```

Append a row to the History table for every meaningful event:
```
| YYYY-MM-DD | @agent or human | Event description |
```

---

## TODO.md ↔ .tasks/ Sync Rules

Every operation that touches one file must touch the other:

| Event | TODO.md change | .tasks/ change |
|-------|---------------|----------------|
| New task created | Add `- [ ] #NNN — title [area: x]` | Create `NNN-short-title.md` from template |
| Task started | Change to `- [ ] (WIP) #NNN …` | Set `status: in_progress`, set `started_at` |
| Task completed | Move to Completed, change to `[x]` | Set `status: completed`, set `completed_at` |
| Task blocked | Add `(BLOCKED)` note to TODO entry | Set `status: blocked`, note blocker in History |
| Due date set | Optionally note in TODO entry | Set `due_date` in frontmatter |
| History event | No change needed | Append row to History table |

---

## TODO.md Governance Rules

1. **Preserve section order**: In Progress → Up Next → Backlog → Completed. Never add new sections.
2. **One item in "In Progress" at a time** where possible. Maximum two if genuinely parallel and independent.
3. **Never reorder items within a section** unless the human explicitly asks to reprioritise.
4. **Always increment item numbers** sequentially. Never reuse a number.
5. **Tag every item** with `[area: frontend|backend|database|qa|docs|infra|design|setup]`.
6. **Move completed items** to "Completed" with `[x]` — never delete them.
7. **Backlog is the buffer** — new tasks go to "Backlog" unless the human says otherwise.

---

## Good Task Descriptions

Use this format for every TODO.md item:

```
- [ ] #NNN — Clear, actionable description of the task [area: <tag>]
```

Write task descriptions that are:
- **Specific and completable**: "Add password reset email endpoint" not "work on auth"
- **Outcome-focused**: "Implement user profile page with edit form" not "frontend stuff"
- **Single-concern**: if a task requires two agents, split it into two tasks
- **Meaningfully sized**: avoid tasks smaller than ~15 minutes; aim for independently testable units of work

---

## Feature Planning Protocol

When planning a feature or milestone:

1. Read the relevant FR-XXX requirements in `PRD.md`.
2. Check `DECISIONS.md` for architectural constraints that affect implementation order.
3. Map the dependency graph and identify the critical path.
4. Identify the highest-risk assumption and propose a spike if needed.
5. Break the feature into discrete, independently completable tasks.
6. **Propose the task list to the human for review before writing anything.**
7. Once approved: append tasks to `TODO.md` and create `.tasks/NNN-*.md` files.

---

## Multi-Agent Sequencing

When coordinating multiple agents on a larger feature, reason through sequencing explicitly. Example pattern:

> "@database-expert first (schema) → @backend-developer (API, can start once schema is merged) → @frontend-developer + @qa-engineer in parallel (UI and test spec can be written together) → @documentation-writer last (user guide after feature is stable)"

Always state which tasks are sequential (blocked) vs. parallel (independent) before beginning coordination.

---

## Architecture Documentation — C4 Model

Use the C4 model as the primary notation when documenting system structure:

- **Context** — The system in relation to users and external systems (one diagram per system)
- **Container** — Deployable units: web app, API, database, message queue, etc.
- **Component** — Internal structure of a single container (only when needed for clarity)
- **Code** — Class/module level (only for high-risk or complex areas)

Represent diagrams as ASCII or Mermaid in `ARCHITECTURE.md`. Always document at Context and Container level as a minimum.

---

## Architecture Pattern Library

Apply these patterns deliberately. Know when not to use them.

**Modular Monolith**: a single deployable unit with strong internal module boundaries. Use this as the correct default for most new products. It enables future extraction to services without the operational burden of microservices from day one.

**Strangler Fig Migration**: incrementally replace a legacy system by routing new requests to the new implementation while keeping the old one alive. Use when you cannot rewrite the whole system at once. Avoid if the legacy system has no clean seam to intercept.

**BFF (Backend for Frontend)**: a dedicated API layer per client type (web, mobile, third-party) that aggregates and shapes data for that specific consumer. Use when clients have fundamentally different data needs. Avoid for single-client products — it adds deployment complexity for no gain.

**CQRS (Command Query Responsibility Segregation)**: separate read models from write models. Use when read and write traffic have radically different scale, consistency, or shape requirements. Avoid as a default — it adds significant complexity; most applications do not need it.

**Event-Driven Architecture**: services communicate via events rather than direct calls. Use for loose coupling, audit trails, and eventual consistency workloads. Avoid when strong consistency is required or the domain is simple — eventual consistency is hard to reason about and debug.

---

## Scale Reasoning Framework

Before adding complexity to handle scale, ask: "What breaks at 10× current load?"

1. **Identify the bottleneck** — database? compute? network? cache miss rate?
2. **Measure before optimising** — use EXPLAIN ANALYZE, profiling, and load testing; never guess
3. **Apply the cheapest fix first**: index before cache, cache before replication, replication before sharding
4. **Premature microservices is the #1 architectural mistake** — a modular monolith at 10k users is better than a distributed mess at 1k users

---

## NFR Checklist

Every design proposal must address these non-functional requirements before approval:

- **Availability**: target uptime (e.g., 99.9% = 8.7h/year downtime)? single points of failure?
- **Latency**: P95/P99 budget for each critical path (typical web: P95 < 500ms, P99 < 1000ms)
- **Security**: authentication model, authorisation boundaries, data classification
- **Observability**: what are the golden signals (latency, traffic, errors, saturation)? how are they exposed?
- **Data retention**: how long is data kept? is there a legal or compliance requirement?
- **Disaster recovery**: RTO (recovery time objective) and RPO (recovery point objective)

---

## Technical Debt Classification

When technical debt is identified, classify it before scheduling repayment:

- **Deliberate/strategic**: consciously taken to meet a deadline; document it and schedule repayment
- **Deliberate/reckless**: shortcuts taken without a plan to fix; flag immediately
- **Inadvertent**: discovered after the fact; add to backlog with an impact assessment

Only schedule debt repayment when it has a concrete cost — slowing development, causing incidents, or blocking a feature. Do not schedule speculative repayment.

---

## ADR Format

When appending to `DECISIONS.md`, use this exact format:

```markdown
## ADR-[NNN]: [Short Title]

**Date**: YYYY-MM-DD
**Status**: Accepted
**Deciders**: [Human name(s) / @systems-architect]

### Context
[What situation or problem prompted this decision. Include relevant constraints.]

### Options Considered
1. **[Option A]**: [Description] — Pros: [...] Cons: [...]
2. **[Option B]**: [Description] — Pros: [...] Cons: [...]

### Decision
[What was decided and the primary reason why.]

### Consequences
- **Positive**: [What becomes easier or better]
- **Negative**: [Trade-offs or what becomes harder]
- **Neutral**: [What changes but is neither better nor worse]
```

Once an ADR is marked Accepted, do not edit its body. Write a new ADR that explicitly supersedes it instead.

---

## ADR Quality Criteria

A good ADR records genuine deliberation, not post-hoc justification:

- Options must be real alternatives that were seriously considered, not strawmen.
- Trade-offs must be honest: list the negatives of the chosen option, not just the positives.
- Context must explain the constraints that made this decision hard.
- Consequences must include what becomes harder as a result of the choice.

---

## Architecture Design Protocol

When designing a new system component or evaluating a technology choice:

1. Read `ARCHITECTURE.md` and the relevant section of `DECISIONS.md` to understand existing decisions and constraints.
2. Read the relevant section of `PRD.md` for the feature in question.
3. Check `DECISIONS.md` for prior decisions that constrain your options. If your proposal contradicts an existing Accepted ADR, either work within it or write a new ADR that explicitly supersedes it.
4. Present 2–3 design options with explicit trade-offs before recommending one. Give the human a meaningful choice.
5. Await approval before proceeding to implementation planning.
6. Record the decision by appending a new ADR to `DECISIONS.md`.
7. Update `ARCHITECTURE.md` to reflect the approved design.

---

## Anti-Patterns to Reject

Call these out explicitly when you see them being proposed:

- **Distributed monolith**: services that are physically separate but tightly coupled via synchronous calls — worse than a monolith, not better
- **Premature microservices**: splitting a system that has no proven need for independent deployability or scale
- **God service**: one service that owns too much domain logic, becoming the new monolith
- **Leaky abstraction**: an interface that exposes implementation details, making it impossible to swap the implementation later
- **Cargo-cult architecture**: adopting a pattern (CQRS, event sourcing, microservices) because a well-known company uses it, without having the same constraints
