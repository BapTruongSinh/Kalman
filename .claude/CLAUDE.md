# demo_kalman — Claude Instructions

> Stack: Python · Django · MySQL · React/Vite · ARX artifact · MPC/AMPC controller
> Last updated: 2026-05-08

## Project Context

This repository contains a smart greenhouse research/demo system. `Kalman/` is the live estimator application that ingests sensor samples, uses the ARX artifact as a prior, runs Adaptive Kalman filtering, stores MySQL traces, and serves the dashboard. `MPC/` is the standalone controller project for v2 MPC recommendations and v3 AMPC/closed-loop pilot work.

**Tech stack summary**: React + Vite dashboard · Django REST backend · MySQL/XAMPP local DB · Python ARX/MPC tooling · AWS target deferred

---

## Agents Available

**Mandatory delegation — this is not optional.** Every task that falls within a specialist's domain MUST be routed to that agent. Do not implement code, design schemas, write docs, or configure pipelines yourself — delegate. Only handle directly: project-level questions, routing decisions, and tasks explicitly outside all specialist domains.

| Agent | Role | Invoke when... |
|-------|------|----------------|
| `planner` | Backlog & architecture | "What's next?", sprint planning, feature decomposition, tech decisions, ADRs, new feature design before implementation |
| `builder` | All application code | Frontend components, backend endpoints, database schemas/migrations, React Native screens — specify domain in request |
| `designer` | UX & content | User flows, wireframes, component specs, accessibility, landing copy, SEO, brand voice, marketing content |
| `quality` | Testing & documentation | E2E tests, test strategy, coverage gaps, user guide updates, post-feature documentation |
| `infra` | Infrastructure & pipelines | CI/CD workflows, deployments, Dockerfiles, docker-compose, container configuration |

---

## Critical Rules

These apply to all agents at all times. No exceptions without explicit human instruction.

0. **Project target directories are `Kalman/` and `MPC/`.** Use `Kalman/` for the live estimator/backend/dashboard. Use `MPC/` for the standalone controller project, MPC/AMPC docs, backlog, and future controller code. Use sibling `ARX/` as read-only ARX model/dataset context unless the human explicitly asks to change it. Use `.claude/` only for agent/template management.
1. **Project PRDs require explicit human approval to modify.** Do not edit `Kalman/PRD.md` or `MPC/PRD.md` unless the human has clearly instructed you to do so in the current conversation. Read the relevant PRD to understand requirements.
2. **Project TODO files are living backlogs.** Use `Kalman/TODO.md` for estimator/backend/dashboard work and `MPC/TODO.md` for controller work. Agents may add items, mark items complete, and move items to "Completed". Preserve section order and existing item priority — do not reorder items within a section unless explicitly asked to reprioritize.
3. **All commits use Conventional Commits format** (see Git Conventions below).
4. **Update the relevant project docs** after every significant change before marking a task complete: `Kalman/docs/` for estimator work, `MPC/docs/` for controller work.
5. **Run tests before marking any implementation task complete.**
6. **Never hardcode secrets, credentials, or environment-specific values** in source code.
7. **Consult the relevant `DECISIONS.md`** before proposing changes that may conflict with prior architectural decisions: `Kalman/docs/technical/DECISIONS.md` or `MPC/docs/technical/DECISIONS.md`.
8. **Always delegate to the right specialist.** If a task touches application code (frontend, mobile, backend, or database), design/UX/content, testing/documentation, or infrastructure — invoke the appropriate agent (`builder`, `designer`, `quality`, or `infra`) immediately. Do not implement it yourself. The delegation table above is binding, not advisory.
9. **Commit your own changes; never push.** After completing your work, create a local commit (Conventional Commits format). Do not `git push`. The orchestrator is responsible for pushing the branch and opening the PR.
10. **When invoking `builder`, specify the domain in your request** (e.g. "frontend task — add dark mode toggle" or "database task — add index on orders table"). The builder reads the corresponding skill before starting work.
11. **Read rules, review memory, and codebase onboarding before every new prompt/task.** Before any action or answer, read `.claude/.claude/rules/`, then `.claude/.claude/review/REVIEW.md`, then the relevant onboarding file: `Kalman/docs/technical/CODEBASE_ONBOARDING.md` for estimator/backend/dashboard or `MPC/docs/technical/CODEBASE_ONBOARDING.md` for controller work, then the matching TODO and `.tasks/` files.
12. **Project TODO files are the task source of truth.** Use `Kalman/TODO.md` + `Kalman/.tasks/NNN-*.md` for Kalman work, and `MPC/TODO.md` + `MPC/.tasks/NNN-*.md` for MPC/AMPC controller work. Do not require a plan/discussion workflow or human plan-approval gate before creating or updating tasks unless the human explicitly asks for that workflow.
13. **Review memory after every prompt/window/task.** At the end of each prompt, work window, or task, append a concise entry to `.claude/.claude/review/REVIEW.md` with files changed, verification, residual risk, and next step.
14. **Current project direction is Adaptive Kalman + AMPC.** Do not reduce the project back to baseline Kalman + fixed MPC. Use ARX as the first prediction baseline, keep prediction/estimator modules replaceable, and preserve AMPC state/control/disturbance/cost/safety contracts in docs and task design.
15. **Combine skills when that improves the work.** Prefer project-local skills under `.claude/` when there is overlap, but you may combine them with skills from `C:\Users\ADMIN\.codex\skills` and `C:\Users\ADMIN\.agents\skills` when those external skills are stronger or complementary. If multiple skills fit and can work together, combine them rather than forcing a single-skill path. For code understanding, tracing, or architecture analysis before changes, you may additionally use `C:\Users\ADMIN\.agents\skills\understand` and `C:\Users\ADMIN\.agents\skills\understand-explain`.
16. **Update `CODEBASE_ONBOARDING.md` only after user review approval.** Use the relevant onboarding file as mandatory preflight context before implementation, but after coding, wait until the user reviews and confirms OK before documenting accepted flow changes there.

---

## Slash Commands

Use these commands to trigger common multi-step workflows:

| Command | What it does |
|---------|--------------|
| `/orchestrate <task>` | Full multi-agent task execution — decompose, plan, branch, execute in waves |
| `/status` | Render a live project health card (tasks, commits, open PRs, blockers) |
| `/start` | Run project onboarding from `START_HERE.md` |
| `/sync-template` | Pull latest agent definitions and templates from upstream |

---

## MCP Servers

Project MCP servers are declared in `.mcp.json` (committed to the repo — shared by the whole team). No extra credentials required — both servers are unauthenticated.

| Server | Purpose | Agents that use it |
|--------|---------|-------------------|
| `sequential-thinking` | Structured multi-step reasoning scratchpad | `planner` |
| `context7` | Live, version-accurate library documentation | `builder`, `infra` |

**GitHub integration** — use the `gh` CLI (already authenticated via `gh auth login`). All agents with `Bash` access can run `gh` commands directly. No token configuration needed.

---

## File-Scoped Rules

Rules in `.claude/rules/` inject context automatically based on the file being edited:

| Rule file | Applied to | Key standards |
|-----------|-----------|---------------|
| `typescript.md` | `*.ts`, `*.tsx` | No `any`, no `!` assertions, no `console.log`, explicit return types |
| `migrations.md` | `*.sql`, `migrations/**` | Reversible migrations, naming convention, no destructive ops without guards |
| `tests.md` | `*.spec.ts`, `*.test.ts`, `tests/**` | Page Object Model, `data-testid` selectors, no `test.only`, 80% coverage |

---

## Project Structure

```
Kalman/                 # Live estimator/backend/dashboard project
  backend/              # Django backend, MySQL models, live ingestion, Kalman/ARX runtime
  dashboard/            # React + Vite dashboard
  docs/
    user/USER_GUIDE.md  # User-facing documentation
    technical/          # Architecture, API, DB, decisions, design system
    content/            # Content strategy, brand voice, keyword targets
  .tasks/               # Detailed task files — one per TODO item or task group
MPC/                    # Controller project: MPC/AMPC docs, backlog, future Python package and CLI
  docs/
  .tasks/
  PRD.md
  TODO.md
  CLAUDE.md
ARX/                    # ARX model/dataset context for Kalman implementation
.claude/
  agents/               # Specialist agent definitions
  commands/             # Slash commands (/orchestrate, /status, /start, /sync-template)
  review/               # Review memory; read before work and append after prompts/windows/tasks
  rules/                # File-scoped rules (typescript, migrations, tests)
  skills/               # Domain skill files loaded by agents (frontend, backend, database, mobile, etc.)
  .claude-plugin/       # Plugin manifest — makes skills available when symlinked into ~/.claude/plugins/
  settings.json         # Claude Code settings
  templates/            # Blank doc templates (synced from upstream — do not edit)
.mcp.json               # Project MCP server configuration (shared with team)
```

---

## Git Conventions

### Commit Format
```
<type>(<scope>): <short description>

[optional body]
[optional footer: Closes #issue]
```

**Types**: `feat` · `fix` · `docs` · `style` · `refactor` · `test` · `chore` · `perf` · `ci`

Examples:
```
feat(auth): add OAuth2 login with Google
fix(api): handle null response from payment provider
docs(user-guide): update onboarding section after flow change
```

### Branch Naming
```
feature/<ticket-id>-short-description
fix/<ticket-id>-short-description
chore/<description>
docs/<description>
refactor/<description>
```

### PR Requirements

> **Workflow note:** Specialist agents commit locally; the orchestrator pushes and opens the PR.

- PR title follows Conventional Commits format
- Fill out `.github/PULL_REQUEST_TEMPLATE.md` completely — do not delete sections
- Link to the related issue/ticket (`Closes #XXX`)
- At least one reviewer required before merge
- All CI checks must pass

---

## Code Style

- **Backend/MPC language**: Python 3, typed dataclasses where useful, explicit error handling.
- **Dashboard language**: TypeScript with React + Vite.
- **Formatter/linter**: follow existing project tooling in each subproject; do not introduce a new formatter without a task.
- **Import style**: keep imports local and explicit; avoid hidden coupling between `Kalman/`, `MPC/`, and `ARX/`.
- **No hardcoded secrets** in source, tests, docs, or review memory.
- **No commented-out code** committed — delete it or track it in the relevant project TODO.

---

## Testing Conventions

- **Kalman backend**: `cd Kalman/backend; python -m pytest estimation/tests -q`.
- **Kalman Django checks**: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py migrate --check`.
- **Kalman dashboard**: `cd Kalman/dashboard; npm test -- --run; npm run build`.
- **MPC controller**: `python -m pytest MPC/tests -q` after runtime package exists.
- **Completion gates**: each task must pass Logic, Nghiệp vụ, Security, and Test chạy thực tế gates before completion.

---

## Environment & Commands

- **Kalman backend dev**: `cd Kalman/backend; python manage.py runserver`.
- **Kalman backend tests**: `cd Kalman/backend; python -m pytest estimation/tests -q`.
- **Kalman dashboard dev**: `cd Kalman/dashboard; npm run dev`.
- **Kalman dashboard tests/build**: `npm test -- --run`; `npm run build`.
- **MPC tests target**: `python -m pytest MPC/tests -q`.
- **Database**: MySQL/XAMPP for Kalman runtime; no SQLite override.

---

## Key Documentation

@Kalman/docs/technical/ARCHITECTURE.md
@Kalman/docs/technical/DESIGN_SYSTEM.md
@Kalman/docs/technical/DECISIONS.md
@Kalman/docs/technical/ONBOARDING_ANSWERS.md
@Kalman/docs/technical/CODEBASE_ONBOARDING.md
@Kalman/docs/technical/ADAPTIVE_KALMAN_AMPC_NOTES.md
@Kalman/docs/technical/API.md
@Kalman/docs/technical/DATABASE.md
@Kalman/docs/user/USER_GUIDE.md
@MPC/PRD.md
@MPC/TODO.md
@MPC/docs/technical/ONBOARDING_ANSWERS.md
@MPC/docs/technical/CODEBASE_ONBOARDING.md
@MPC/docs/technical/ARCHITECTURE.md
@MPC/docs/technical/DECISIONS.md
@MPC/docs/technical/CONFIG.md
