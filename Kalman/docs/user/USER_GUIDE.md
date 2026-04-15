<!--
DOCUMENT METADATA
Owner: @documentation-writer
Update trigger: Any user-facing workflow is added, changed, or removed
Read by: @qa-engineer
-->

# Adaptive Kalman + AMPC — User Guide (v1)

> Last updated: 2026-04-15
> Version: 0.3.0

This guide explains how to **run the v1 demo**: view persisted experiments in the dashboard, optionally **replay `../../ARX/greenhouse_data.csv` into MySQL** (from `Kalman/backend/`) via a Django shell recipe, and where to read the **methodology** for academic defense.

**Methodology (thesis / report narrative)**: [`../technical/METHODOLOGY_V1.md`](../technical/METHODOLOGY_V1.md)

---

## 1. Prerequisites

| Requirement | Notes |
|-------------|--------|
| Python 3.10+ | Same major as backend tests |
| Node.js + npm | For `Kalman/dashboard` (Vite) |
| MySQL (e.g. XAMPP) | Backend `DATABASES` host from `Kalman/backend/.env` |
| Dataset file | Repo root `ARX/greenhouse_data.csv`; from `Kalman/backend/` use `../../ARX/greenhouse_data.csv` |

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

4. In the sidebar **Experiment runs**, select a run. The main panel shows **raw vs ARX predicted vs Kalman filtered** series (Recharts), slice filters, and **evaluation metrics** when summaries exist.

If the list is empty, populate a run using §4 (shell replay) or run the test suite (tests create runs in the test database only).

---

## 3. API-only workflow (no dashboard)

With Django running, JSON endpoints are documented in [`../technical/API.md`](../technical/API.md):

| Endpoint | Purpose |
|----------|---------|
| `GET /api/runs/` | Last 50 runs |
| `GET /api/runs/{id}/series/` | Time series for charts (`slice`, `limit`, `stride` query params) |
| `GET /api/runs/{id}/metrics/` | Per-slice `EvaluationSummary` metrics |

Base URL in dev: `http://127.0.0.1:8000/api/`.

---

## 4. Offline CSV → full pipeline → MySQL (reference shell replay)

There is **no** `manage.py replay_csv` command in v1; the supported pattern is the same sequence the codebase uses in tests: **ingest → split → validate → preprocess → train ARX → `AdaptiveKalmanCycle.replay` → `map_result_to_cycle` → `bulk_save_cycles` → `evaluate_all_slices`**.

Below is a **minimal reference script** you can paste into `python manage.py shell`. **Change directory to `Kalman/backend/` first** so dataset resolution and Django settings paths match the project layout.

It uses the real greenhouse CSV. **Warning**: the full file has ~105k rows; the first run may take noticeable time and grow `pipeline_cycles`. For a quicker lab demo, replace the `load_csv` line with a bounded slice, e.g. `raw = load_csv(csv_path)[:8000]`, then call `split_chronological(raw)` on that subset.

```python
from pathlib import Path

from estimation.evaluation import evaluate_all_slices
from estimation.ingestion import apply_preprocessing, load_csv, split_chronological, validate_batch
from estimation.kalman import AdaptiveKalmanCycle
from estimation.models import ExperimentRun
from estimation.pipeline import begin_run, bulk_save_cycles, end_run, map_result_to_cycle
from estimation.prediction import ARXPredictionAdapter
from estimation.run_config import RunConfig, create_run

# Resolve CSV: cwd should be Kalman/backend → repo root is parents[1]
csv_path = Path.cwd().resolve().parent.parent / "ARX" / "greenhouse_data.csv"
raw = load_csv(csv_path)
split = split_chronological(raw)
ordered = split.train + split.validation + split.test
slice_tags = (
    ["train"] * len(split.train)
    + ["validation"] * len(split.validation)
    + ["test"] * len(split.test)
)
vals = validate_batch(ordered)
proc = apply_preprocessing(ordered, vals, policy="keep_last")
x0 = float(proc[0].soil_moisture) if proc[0].soil_moisture is not None else 55.0
cfg = RunConfig(
    name="greenhouse_offline_demo",
    dataset_source=str(csv_path.resolve()),
    x0=x0,
    preprocessing_policy="keep_last",
)
adapter = ARXPredictionAdapter(cfg.to_arx_train_config())
adapter.train(
    proc[: len(split.train)],
    val_records=proc[len(split.train) : len(split.train) + len(split.validation)],
)
run = create_run(cfg)
begin_run(run)
est = AdaptiveKalmanCycle(cfg.to_kalman_config(), adapter=adapter)
results = est.replay(proc)
cycles = [
    map_result_to_cycle(res, run, slice_type=sl, record=pr)
    for res, sl, pr in zip(results, slice_tags, proc, strict=True)
]
bulk_save_cycles(cycles, batch_size=500)
evaluate_all_slices(run.pk)
end_run(run, ExperimentRun.Status.COMPLETED)
print("Run id:", run.pk, "status:", run.status)
```

If `Path.cwd()` is not `Kalman/backend`, set `csv_path` explicitly, e.g. `csv_path = Path(r"D:\path\to\Demo_kalman\ARX\greenhouse_data.csv")`.

After `COMPLETED`, refresh the dashboard and select the printed **`run.id`**.

---

## 5. Reproduce results without the database (tests / in-memory)

- **Ingestion smoke (real CSV)**: `pytest estimation/tests/test_ingestion.py::TestEndToEndIngestion::test_full_pipeline_on_real_data -v`
- **Kalman robustness (CSV + replay)**: `pytest estimation/tests/test_pipeline_robustness.py -v`

These prove the same public CSV path and pipeline stages; they use the **test** database or temp files, not your dev MySQL.

**Before a public / production deploy**

- Install dev tools: `pip install -r requirements-dev.txt`
- **Dependency audit**: `pip-audit -r requirements.txt` (expect “No known vulnerabilities” or upgrade pins from the report).
- **Django deploy checks** (after exporting real production env, including a long `DJANGO_SECRET_KEY`): `python manage.py check --deploy`. See `Kalman/backend/.env.example` for `DJANGO_ENV=production`, CORS (comma or whitespace separated origins), CSRF trusted origins, and `DASHBOARD_REQUIRE_AUTH` (defaults **on** in production; set `false` only if reads must stay public).
- After pulling backend changes that add `django.contrib.sessions`, run `python manage.py migrate` once so MySQL has the `django_session` table.

---

## 6. Evaluation artefacts (after a DB replay)

From Django shell or application code (see `estimation.evaluation.reporter`):

- `build_text_report(run_id)` — human-readable report including ADR-003 gate lines.
- `export_to_csv(run_id, output_path)` — metrics tables; `output_path` is a **file** path (e.g. `Path("reports") / "metrics.csv"`), not a directory.
- `export_plots(run_id, output_dir)` — PNG diagnostics if `matplotlib` imports cleanly (`output_dir` is a directory).

---

## 7. Expected demo evidence (targets)

See [`../technical/METHODOLOGY_V1.md`](../technical/METHODOLOGY_V1.md) §4 and project PRD for metric definitions. Targets include high cycle success rate, latency budgets, variance reduction on held-out **test** slice, and bounded innovations — **exact thresholds** are in ADR-003 / `EvaluationSummary` flags.

---

## 8. Common issues

| Symptom | Check |
|---------|--------|
| `FileNotFoundError` on CSV | Path relative to `Kalman/backend/` → `../../ARX/greenhouse_data.csv` (repo root `ARX/…`) |
| Dashboard empty | No completed runs in dev DB — run §4 or insert fixtures |
| `RunStateError` on `begin_run` | Run must be `pending`; only one successful `begin_run` per run |
| `matplotlib` / NumPy errors on `export_plots` | Optional dependency; upgrade/downgrade pair or skip plots |
| CORS / API errors from browser | Use Vite dev server (`5173`) so `/api` proxy applies, or enable CORS for direct `:8000` access |

---

## 9. Academic pointers

1. **What we implemented**: offline replayable estimation with ARX + adaptive-**R** Kalman layer, MySQL traceability, dashboard visualization, automated evaluation (task #005–#009, #011).
2. **What we document for AMPC**: state / control / disturbance / cost / safety **contracts** — see [`../technical/AMPC_MODELING_HANDOFF.md`](../technical/AMPC_MODELING_HANDOFF.md) (task #013).
3. **What we defer**: closed-loop MPC solve and production control — **not** “dropping AMPC from the project”, only deferring **implementation**.
