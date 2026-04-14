# [Project Name] — Claude Instructions

> Stack: [e.g., Next.js 14 · TypeScript · PostgreSQL · Prisma · Railway]
> Last updated: [YYYY-MM-DD]

## Project Context

[2–3 sentences: what this product does, who it serves, and the core problem it solves.]

**Tech stack summary**: [Frontend] · [Backend] · [Database] · [Hosting]

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

0. **Project target directory is `Kalman/`.** Use `Kalman/` as the working project root for code, project docs, backlog, and task files. Use sibling `ARX/` as read-only ARX model/dataset context unless the human explicitly asks to change it. Use `.claude/` only for agent/template management.
1. **`Kalman/PRD.md` requires explicit human approval to modify.** Do not edit it unless the human has clearly instructed you to do so in the current conversation. Read it to understand requirements.
2. **`Kalman/TODO.md` is the living backlog.** Agents may add items, mark items complete, and move items to "Completed". Preserve section order and existing item priority — do not reorder items within a section unless explicitly asked to reprioritize.
3. **All commits use Conventional Commits format** (see Git Conventions below).
4. **Update the relevant `Kalman/docs/` file** after every significant change before marking a task complete.
5. **Run tests before marking any implementation task complete.**
6. **Never hardcode secrets, credentials, or environment-specific values** in source code.
7. **Consult `Kalman/docs/technical/DECISIONS.md`** before proposing changes that may conflict with prior architectural decisions.
8. **Always delegate to the right specialist.** If a task touches application code (frontend, mobile, backend, or database), design/UX/content, testing/documentation, or infrastructure — invoke the appropriate agent (`builder`, `designer`, `quality`, or `infra`) immediately. Do not implement it yourself. The delegation table above is binding, not advisory.
9. **Commit your own changes; never push.** After completing your work, create a local commit (Conventional Commits format). Do not `git push`. The orchestrator is responsible for pushing the branch and opening the PR.
10. **When invoking `builder`, specify the domain in your request** (e.g. "frontend task — add dark mode toggle" or "database task — add index on orders table"). The builder reads the corresponding skill before starting work.
11. **Read rules and review memory before every new prompt/task.** Before any action or answer, read `.claude/.claude/rules/`, then `.claude/.claude/review/REVIEW.md`, then relevant `Kalman/TODO.md` and `Kalman/.tasks/` files.
12. **`Kalman/TODO.md` is the task source of truth.** Use `Kalman/TODO.md` and matching `Kalman/.tasks/NNN-*.md` files for task tracking. Do not require a plan/discussion workflow or human plan-approval gate before creating or updating tasks unless the human explicitly asks for that workflow.
13. **Review memory after every prompt/window/task.** At the end of each prompt, work window, or task, append a concise entry to `.claude/.claude/review/REVIEW.md` with files changed, verification, residual risk, and next step.
14. **Current project direction is Adaptive Kalman + AMPC.** Do not reduce the project back to baseline Kalman + fixed MPC. Use ARX as the first prediction baseline, keep prediction/estimator modules replaceable, and preserve AMPC state/control/disturbance/cost/safety contracts in docs and task design.

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
Kalman/                 # Project target directory: code, docs, backlog, tasks
  src/                  # Application source code
  app/                  # [e.g., Next.js App Router pages]
  components/           # Shared UI components
  lib/                  # Utilities, helpers, shared logic
  tests/
    e2e/                # Playwright E2E tests (*.spec.ts)
  docs/
    user/USER_GUIDE.md  # User-facing documentation
    technical/          # Architecture, API, DB, decisions, design system
    content/            # Content strategy, brand voice, keyword targets
  .tasks/               # Detailed task files — one per TODO item or task group
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

> Fill in when project tooling is set up.

- **Language**: TypeScript (strict mode)
- **Formatter**: [Prettier — config in `.prettierrc`]
- **Linter**: [ESLint — config in `.eslintrc`]
- **Import style**: [absolute imports from `src/`]
- **No `console.log`** in production code — use the project logger utility
- **No commented-out code** committed — delete it or track it in `Kalman/TODO.md`

---

## Testing Conventions

> Fill in when test infrastructure is set up.

- **Unit tests**: [Vitest — colocated as `*.test.ts` next to source files]
- **E2E tests**: [Playwright — in `tests/e2e/*.spec.ts`]
- **Run unit**: `[npm test]`
- **Run E2E**: `[npm run test:e2e]`
- **Coverage target**: 80% for new features
- E2E tests use Page Object Model pattern and `data-testid` selectors

---

## Environment & Commands

> Fill in when project is initialized.

- **Node**: [x.x.x] (see `.nvmrc`)
- **Package manager**: [npm / pnpm / yarn]
- `[npm run dev]` — start dev server
- `[npm run build]` — production build
- `[npm test]` — unit tests
- `[npm run test:e2e]` — E2E tests
- `[npm run lint]` — lint check
- `[npm run typecheck]` — TypeScript check

---

## Key Documentation

@Kalman/docs/technical/ARCHITECTURE.md
@Kalman/docs/technical/DESIGN_SYSTEM.md
@Kalman/docs/technical/DECISIONS.md
@Kalman/docs/technical/ONBOARDING_ANSWERS.md
@Kalman/docs/technical/ADAPTIVE_KALMAN_AMPC_NOTES.md
@Kalman/docs/technical/API.md
@Kalman/docs/technical/DATABASE.md
@Kalman/docs/user/USER_GUIDE.md
