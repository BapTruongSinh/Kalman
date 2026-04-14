---
name: cicd
description: >
  Use when creating or modifying GitHub Actions workflows, setting up deployment pipelines,
  configuring branch protection rules, managing GitHub environments and secrets, automating
  releases and changelogs, optimizing pipeline performance, or debugging CI failures.
---

## Working Protocol

When creating or modifying a pipeline:

1. **Understand the deployment target**: Read `ARCHITECTURE.md` to confirm environments and hosting platform before writing any workflow.
2. **Check existing workflows**: Glob `.github/workflows/` to understand what already exists. Never duplicate a job.
3. **Check decisions log**: Read `DECISIONS.md` for prior CI/CD decisions before proposing changes.
4. **Design the pipeline**: Structure jobs with clear responsibilities — lint/typecheck, test, build, deploy. Separate jobs that can run in parallel. Gate deployments behind required checks.
5. **Implement the workflow**: Write or update the workflow YAML following the standards below.
6. **Validate YAML syntax**: Run `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/<file>.yml'))"` to catch syntax errors before committing.
7. **Update CICD.md**: Document purpose, triggers, required secrets, and environment variables.
8. **Verify secrets and environments**: List required secrets in the PR description so the human can confirm they are configured in GitHub before the workflow runs.

## Pipeline Design Principles

- **Fast feedback first**: developers should know if their PR breaks the build in under 2 minutes. Lint and typecheck must run in the first job and fail fast.
- **Parallelise independent jobs**: lint, unit tests, and type checking can run in parallel — do not chain them sequentially.
- **Cache aggressively**: dependency installation is the most expensive repeatable step. Cache it at the dependency hash level (see below).
- **Gate deployments on required checks**: production deploys must require CI passing + human approval via GitHub Environments.
- **Fail loudly**: never use `continue-on-error: true` to hide failures — fix the root cause.

## Security Scanning in CI

Every CI pipeline must include:

```yaml
- name: Dependency vulnerability audit
  run: npm audit --audit-level=high   # Fail on high/critical vulnerabilities

- name: Static analysis (CodeQL)
  uses: github/codeql-action/analyze@v3
  with:
    languages: javascript, typescript

- name: Container image scan (if Docker is used)
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.IMAGE_TAG }}
    exit-code: 1
    severity: CRITICAL,HIGH
```

Block merges on critical/high vulnerabilities. Document in CICD.md which tool covers which threat category.

## Reusable Workflows

Extract shared logic into reusable workflows to avoid duplication across workflow files:

```yaml
# .github/workflows/reusable-setup-node.yml
on:
  workflow_call:
    inputs:
      node-version-file:
        required: false
        type: string
        default: '.nvmrc'

jobs:
  setup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: ${{ inputs.node-version-file }}
          cache: npm
      - run: npm ci
```

Call reusable workflows with `uses: ./.github/workflows/reusable-setup-node.yml`.

## Release Automation

Use **release-please** (Google) or **semantic-release** to automate versioning and changelogs from Conventional Commits:

```yaml
# .github/workflows/release.yml
on:
  push:
    branches: [main]

jobs:
  release:
    uses: googleapis/release-please-action@v4
    with:
      release-type: node
      # Reads Conventional Commits to determine semver bump
      # Creates a release PR automatically
      # Tags the release when the PR is merged
```

This eliminates manual version bumps and ensures CHANGELOG.md is always current. Requires the team to follow Conventional Commits.

## Deployment Strategies

Choose the right strategy based on risk and infrastructure:

| Strategy | When to use | How to implement |
|----------|-------------|-----------------|
| **Rolling** | Stateless services, downtime acceptable | Default on most platforms (Railway, Render, Fly.io) |
| **Blue-green** | Zero-downtime required, easy rollback needed | Two identical environments; switch traffic via DNS/load balancer |
| **Canary** | High-risk changes, gradual rollout needed | Route X% of traffic to new version; increase after validation |

For most projects at early stage: rolling deploys with a post-deploy smoke test and automatic rollback on health check failure is the right balance.

## Post-Deploy Observability

After every production deploy:

```yaml
- name: Smoke test
  run: |
    sleep 10  # Wait for service to start
    curl --fail ${{ vars.PRODUCTION_URL }}/health || exit 1

- name: Notify deployment
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "Deployed ${{ github.sha }} to production ✓"
      }
```

Configure auto-rollback in the hosting platform (Railway, Fly.io, etc.) to trigger when health checks fail for N consecutive checks after deployment.

## Cache Key Strategy

Dependency hash → code hash → fallback — never the reverse:

```yaml
- uses: actions/setup-node@v4
  with:
    node-version-file: .nvmrc
    cache: npm          # Keyed on package-lock.json hash automatically

- uses: actions/cache@v4
  with:
    path: .next/cache
    key: ${{ runner.os }}-nextjs-${{ hashFiles('package-lock.json') }}-${{ hashFiles('**/*.ts','**/*.tsx') }}
    restore-keys: |
      ${{ runner.os }}-nextjs-${{ hashFiles('package-lock.json') }}-
      ${{ runner.os }}-nextjs-
```

**Never cache**: test results, build artefacts that embed environment-specific values, or anything that changes between branches.

## Workflow Design Standards

### File naming
```
.github/workflows/
  ci.yml          # Lint, typecheck, unit tests — every PR
  e2e.yml         # End-to-end tests — PRs to main/staging
  deploy.yml      # Deployment — merge to main/staging
  release.yml     # Release automation — version tags
  security.yml    # Scheduled security scans
```

### Required job structure
```yaml
name: [Descriptive workflow name]

on:
  [trigger]:
    branches: [branch filters]

jobs:
  [job-name]:
    name: [Human-readable job name]
    runs-on: ubuntu-latest
    timeout-minutes: 15       # Always set — prevents runaway jobs
    steps:
      - uses: actions/checkout@v4
      - name: [Step description]
        run: [command]
```

### Environment and secrets
- Reference secrets as `${{ secrets.SECRET_NAME }}` — never hardcode values
- Use `vars.` (repository variables) for non-sensitive config; `secrets.` for credentials
- Use GitHub Environments for production deployments with required reviewer approval gates
- Document every required secret in `CICD.md` under a "Required Secrets" section

### Deployment gates
- Production deploys: CI passing + at least one reviewer approval via `environment: production`
- Always include a rollback step or document the manual rollback procedure in `CICD.md`

## CICD.md Update Format

```markdown
## [workflow-name].yml

**Trigger**: [e.g., Push to `main`, PR opened against `main`]
**Purpose**: [What this workflow does and why]

### Jobs
| Job | Runs when | Description |
|-----|-----------|-------------|
| [job-name] | always | [what it does] |

### Required Secrets
| Secret | Where to set | Description |
|--------|-------------|-------------|
| `SECRET_NAME` | GitHub repo → Settings → Secrets | [what it's used for] |

### Required Variables
| Variable | Value | Description |
|----------|-------|-------------|
| `PRODUCTION_URL` | `https://...` | Used for smoke tests after deploy |
```

## Anti-Patterns

- **Secrets in workflow YAML** — even in `echo` or `run` steps; they appear in logs; always use `${{ secrets.NAME }}`
- **`continue-on-error: true`** to silence failures — masks real problems; fix the underlying issue
- **Self-hosted runners without isolation** — a compromised workflow can persist malicious state between runs; use ephemeral runners
- **Unbounded job timeouts** — a hung job blocks the queue; always set `timeout-minutes`
- **Downloading untrusted actions without pinning to a commit SHA** — `uses: some-action@v1` can be hijacked; pin to `uses: some-action@abc1234` for actions outside the GitHub org
- **Deploying on every push to main without a staging gate** — always deploy to staging first and run smoke tests before promoting to production
