<!--
DOCUMENT METADATA
Owner: @documentation-writer
Update trigger: Any user-facing workflow is added, changed, or removed
Read by: @qa-engineer
-->

# Adaptive Kalman + AMPC — User Guide (v1)

> Last updated: 2026-05-09
> Version: 0.5.0

This guide explains how to **run the v1 demo**: send live samples through the authenticated online ingestion endpoint, view persisted experiments in the dashboard, run AMPC recommendations for one greenhouse, and read the **methodology** for academic defense.

**Methodology (thesis / report narrative)**: [`../technical/METHODOLOGY_V1.md`](../technical/METHODOLOGY_V1.md)

---

## 1. Prerequisites

| Requirement | Notes |
|-------------|--------|
| Python 3.10+ | Same major as backend tests |
| Node.js + npm | For `Server/dashboard` (Vite) |
| MySQL (e.g. XAMPP) | Backend `DATABASES` host from `Server/backend/.env` |
| Dataset file | Repo root `ARX/greenhouse_data.csv`; from `Server/backend/` use `../../ARX/greenhouse_data.csv` |
| Runtime ARX artifact | Repo root `ARX/arx_model.json`; override with `ARX_MODEL_PATH` if needed |

Install backend dependencies (from **`Server/backend/`**):

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Copy `Server/backend/.env.example` → `.env` and set `DATABASE_URL` / Django DB variables to match MySQL.

Apply migrations:

```bash
cd Server/backend
python manage.py migrate
```

(Optional) Create a DRF token for **live** ingestion demos — see [`../technical/API.md`](../technical/API.md) § Live Ingestion.

---

## 2. Run the dashboard demo (view existing runs)

1. **Terminal A — Django API** (port 8000):

```bash
cd Server/backend
python manage.py runserver 127.0.0.1:8000
```

2. **Terminal B — Vite dev server** (port 5173; proxies `/api` → Django):

```bash
cd Server/dashboard
npm install
npm run dev
```

3. Open **`http://127.0.0.1:5173`**.

4. In the sidebar **Experiment runs**, select a run. The main panel shows **raw vs ARX predicted vs Kalman filtered** series (Recharts), the `online` series, and **evaluation metrics** when summaries exist.

If the list is empty, populate a live run through §3. Tests create runs in the test database only.

---

## 3. API-only workflow (no dashboard)

Primary runtime path after ADR-004:

```text
POST /api/ingest/samples/
Authorization: Token <token>
```

Create a `Greenhouse` for the device/user, create a `live` `ExperimentRun` for that greenhouse, move it to `running`, then post samples as documented in `docs/technical/API.md`. The backend authorizes through `Greenhouse.owner`, loads the ARX artifact from `ARX_MODEL_PATH` (default `../../ARX/arx_model.json` from `Server/backend`), and uses it as the Kalman prior once the run has enough previous live samples.

If `arx_model.json` is missing or invalid, ingestion still works with carry-forward Kalman prior and logs an internal warning. Do not send model paths in API payloads.

With Django running, JSON endpoints are documented in [`../technical/API.md`](../technical/API.md):

| Endpoint | Purpose |
|----------|---------|
| `GET /api/runs/` | Last 50 runs; optional `greenhouse_id` filter |
| `GET /api/runs/{id}/series/` | Time series for charts (`slice=online`, `limit`, `stride` query params) |
| `GET /api/runs/{id}/metrics/` | Online `EvaluationSummary` metrics |
| `GET /api/greenhouses/{id}/control-profile/` | Load/create AMPC controller profile |
| `PATCH /api/greenhouses/{id}/control-profile/` | Update whitelisted user-facing AMPC profile fields |
| `POST /api/greenhouses/{id}/ampc/recommendations/` | Run AMPC from latest persisted Kalman state |
| `GET /api/greenhouses/{id}/ampc/recommendations/latest/` | Read latest AMPC recommendation |

Base URL in dev: `http://127.0.0.1:8000/api/`.

---

## 4. Run an AMPC recommendation

AMPC is a Django API path, not a CLI call in production. The request only needs an authenticated user and `greenhouse_id`; the backend verifies ownership, reads the latest valid `PipelineCycle` rows, loads the server-side ARX artifact from `ARX_MODEL_PATH`, applies AMPC bias correction, persists an `AMPCRecommendation`, and returns dashboard JSON.

Minimal POST:

```bash
curl -X POST http://127.0.0.1:8000/api/greenhouses/1/ampc/recommendations/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d "{}"
```

For browser session auth, send the normal Django session cookie and `X-CSRFToken` on `POST` and `PATCH` requests.

Default actuator behavior is recommendation-only: `actuator_enabled=false`, no HTTP command is sent. To pilot hardware later, an operator must configure `GreenhouseControlProfile.actuator_url`, set `actuator_bearer_token_env` to an environment variable name, export that token in the backend process, then enable the profile. API responses never expose the URL token or model path.

Fail-closed cases such as missing state, stale samples, insufficient history, model/solver errors, unsafe recommendations, or actuator HTTP failure are persisted with `pump_seconds=0.0`, a non-`safe` status, and an operator-readable reason. Unsafe recommendations do not send actuator commands.

---

## 5. Reproduce results with tests

- **All backend tests**: `python -m pytest estimation/tests -q`
- **Live ingest**: `python -m pytest estimation/tests/test_live_ingest.py -q`
- **Artifact prediction**: `python -m pytest estimation/tests/test_prediction.py -q`
- **AMPC online integration**: `python -m pytest estimation/tests/test_control_ampc.py -q`
- **MPC package**: from repo root, `python -m pytest MPC/tests -q`

Tests use the Django test database or temp files, not your dev MySQL data.

**Before a public / production deploy**

- Install dev tools: `pip install -r requirements-dev.txt`
- **Dependency audit**: `pip-audit -r requirements.txt` (expect “No known vulnerabilities” or upgrade pins from the report).
- **Django deploy checks** (after exporting real production env, including a long `DJANGO_SECRET_KEY`): `python manage.py check --deploy`. See `Server/backend/.env.example` for `DJANGO_ENV=production`, CORS (comma or whitespace separated origins), CSRF trusted origins, and `DASHBOARD_REQUIRE_AUTH` (defaults **on** in production; set `false` only if reads must stay public).
- After pulling backend changes that add `django.contrib.sessions`, run `python manage.py migrate` once so MySQL has the `django_session` table.

---

## 6. Evaluation artefacts

From Django shell or application code (see `estimation.evaluation.reporter`):

- `evaluate_online(run_id)` — computes and stores the single `online` summary.
- `build_text_report(run_id)` — human-readable online evaluation report.
- `export_to_csv(run_id, output_path)` — metrics tables; `output_path` is a **file** path (e.g. `Path("reports") / "metrics.csv"`), not a directory.
- `export_plots(run_id, output_dir)` — PNG diagnostics if `matplotlib` imports cleanly (`output_dir` is a directory).

---

## 7. Expected demo evidence (targets)

See [`../technical/METHODOLOGY_V1.md`](../technical/METHODOLOGY_V1.md) §4 and project PRD for metric definitions. Targets include high cycle success rate, latency budgets, online variance reduction, and bounded innovations.

---

## 8. Common issues

| Symptom | Check |
|---------|--------|
| Dashboard empty | No live runs in dev DB — create a live run and post samples |
| `RunStateError` on `begin_run` | Run must be `pending`; only one successful `begin_run` per run |
| AMPC returns `state_unavailable` | No valid Kalman cycle exists for that greenhouse yet |
| AMPC returns `stale_sample` | Latest valid sample is older than the control profile's stale threshold |
| AMPC returns `model_error` / `history_too_short` | The greenhouse does not yet have enough valid history for the ARX plant model |
| Actuator shows `config_error` | Profile is enabled but URL/token env configuration is incomplete or unsafe |
| `matplotlib` / NumPy errors on `export_plots` | Optional dependency; upgrade/downgrade pair or skip plots |
| CORS / API errors from browser | Use Vite dev server (`5173`) so `/api` proxy applies, or enable CORS for direct `:8000` access |

---

## 9. Academic pointers

1. **What we implemented**: online estimation with ARX artifact + adaptive-**R** Kalman layer, MySQL traceability, dashboard visualization, automated evaluation.
2. **What we implemented for AMPC**: single-pump AMPC recommendation from DB-sourced Kalman state, ARX artifact, residual bias correction, audit persistence, and optional fail-safe HTTP actuator branch.
3. **What remains future work**: calibrated ET0/ETc/Dr physical water-balance control, multi-actuator policies, production hardware rollout, and cloud deployment.
