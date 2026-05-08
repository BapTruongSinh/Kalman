<!--
DOCUMENT METADATA
Owner: @documentation-writer
Update trigger: Any user-facing workflow is added, changed, or removed
Read by: @qa-engineer
-->

# Adaptive Kalman + AMPC — User Guide (v1)

> Last updated: 2026-05-08
> Version: 0.4.0

This guide explains how to **run the v1 demo**: send live samples through the authenticated online ingestion endpoint, view persisted experiments in the dashboard, and read the **methodology** for academic defense.

**Methodology (thesis / report narrative)**: [`../technical/METHODOLOGY_V1.md`](../technical/METHODOLOGY_V1.md)

---

## 1. Prerequisites

| Requirement | Notes |
|-------------|--------|
| Python 3.10+ | Same major as backend tests |
| Node.js + npm | For `Kalman/dashboard` (Vite) |
| MySQL (e.g. XAMPP) | Backend `DATABASES` host from `Kalman/backend/.env` |
| Dataset file | Repo root `ARX/greenhouse_data.csv`; from `Kalman/backend/` use `../../ARX/greenhouse_data.csv` |
| Runtime ARX artifact | Repo root `ARX/arx_model.json`; override with `ARX_MODEL_PATH` if needed |

Install backend dependencies (from **`Kalman/backend/`**):

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Copy `Kalman/backend/.env.example` → `.env` and set `DATABASE_URL` / Django DB variables to match MySQL.

Apply migrations:

```bash
cd Kalman/backend
python manage.py migrate
```

(Optional) Create a DRF token for **live** ingestion demos — see [`../technical/API.md`](../technical/API.md) § Live Ingestion.

---

## 2. Run the dashboard demo (view existing runs)

1. **Terminal A — Django API** (port 8000):

```bash
cd Kalman/backend
python manage.py runserver 127.0.0.1:8000
```

2. **Terminal B — Vite dev server** (port 5173; proxies `/api` → Django):

```bash
cd Kalman/dashboard
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

Create a `live` `ExperimentRun`, assign its `owner`, move it to `running`, then post samples as documented in `docs/technical/API.md`. The backend loads the ARX artifact from `ARX_MODEL_PATH` (default `../../ARX/arx_model.json` from `Kalman/backend`) and uses it as the Kalman prior once the run has enough previous live samples.

If `arx_model.json` is missing or invalid, ingestion still works with carry-forward Kalman prior and logs an internal warning. Do not send model paths in API payloads.

With Django running, JSON endpoints are documented in [`../technical/API.md`](../technical/API.md):

| Endpoint | Purpose |
|----------|---------|
| `GET /api/runs/` | Last 50 runs |
| `GET /api/runs/{id}/series/` | Time series for charts (`slice=online`, `limit`, `stride` query params) |
| `GET /api/runs/{id}/metrics/` | Online `EvaluationSummary` metrics |

Base URL in dev: `http://127.0.0.1:8000/api/`.

---

## 4. Reproduce results with tests

- **All backend tests**: `python -m pytest estimation/tests -q`
- **Live ingest**: `python -m pytest estimation/tests/test_live_ingest.py -q`
- **Artifact prediction**: `python -m pytest estimation/tests/test_prediction.py -q`

Tests use the Django test database or temp files, not your dev MySQL data.

**Before a public / production deploy**

- Install dev tools: `pip install -r requirements-dev.txt`
- **Dependency audit**: `pip-audit -r requirements.txt` (expect “No known vulnerabilities” or upgrade pins from the report).
- **Django deploy checks** (after exporting real production env, including a long `DJANGO_SECRET_KEY`): `python manage.py check --deploy`. See `Kalman/backend/.env.example` for `DJANGO_ENV=production`, CORS (comma or whitespace separated origins), CSRF trusted origins, and `DASHBOARD_REQUIRE_AUTH` (defaults **on** in production; set `false` only if reads must stay public).
- After pulling backend changes that add `django.contrib.sessions`, run `python manage.py migrate` once so MySQL has the `django_session` table.

---

## 5. Evaluation artefacts

From Django shell or application code (see `estimation.evaluation.reporter`):

- `evaluate_online(run_id)` — computes and stores the single `online` summary.
- `build_text_report(run_id)` — human-readable online evaluation report.
- `export_to_csv(run_id, output_path)` — metrics tables; `output_path` is a **file** path (e.g. `Path("reports") / "metrics.csv"`), not a directory.
- `export_plots(run_id, output_dir)` — PNG diagnostics if `matplotlib` imports cleanly (`output_dir` is a directory).

---

## 6. Expected demo evidence (targets)

See [`../technical/METHODOLOGY_V1.md`](../technical/METHODOLOGY_V1.md) §4 and project PRD for metric definitions. Targets include high cycle success rate, latency budgets, online variance reduction, and bounded innovations.

---

## 7. Common issues

| Symptom | Check |
|---------|--------|
| Dashboard empty | No live runs in dev DB — create a live run and post samples |
| `RunStateError` on `begin_run` | Run must be `pending`; only one successful `begin_run` per run |
| `matplotlib` / NumPy errors on `export_plots` | Optional dependency; upgrade/downgrade pair or skip plots |
| CORS / API errors from browser | Use Vite dev server (`5173`) so `/api` proxy applies, or enable CORS for direct `:8000` access |

---

## 8. Academic pointers

1. **What we implemented**: online estimation with ARX artifact + adaptive-**R** Kalman layer, MySQL traceability, dashboard visualization, automated evaluation.
2. **What we document for AMPC**: state / control / disturbance / cost / safety **contracts** — see [`../technical/AMPC_MODELING_HANDOFF.md`](../technical/AMPC_MODELING_HANDOFF.md) (task #013).
3. **What we defer**: closed-loop MPC solve and production control — **not** “dropping AMPC from the project”, only deferring **implementation**.
