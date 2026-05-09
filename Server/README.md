# Server

`Server/` contains the Django backend and Vite dashboard for the smart greenhouse system.

Responsibilities:

- Authenticated multi-user, multi-greenhouse workflow.
- Live sensor ingestion and persistence.
- Kalman state estimation through the local `kalman` package.
- AMPC recommendation/control integration through the local `mpc` package.
- Recommendation/prediction persistence, dashboard JSON APIs, reporting, and optional actuator execution.

Algorithm code is intentionally outside this folder:

- `../Kalman/` exposes pure Adaptive Kalman modules as `kalman`.
- `../MPC/` exposes pure controller modules as `mpc`.
- `../ARX/arx_model.json` is the monorepo development ARX artifact fallback.

## Setup

From the repo root:

```powershell
cd Server/backend
pip install -r requirements-local.txt
```

Dashboard:

```powershell
cd Server/dashboard
npm install
```

## Run Locally

Backend:

```powershell
cd Server/backend
python manage.py runserver
```

Dashboard:

```powershell
cd Server/dashboard
npm run dev
```

## Checks

```powershell
python -m pytest Kalman/tests -q
cd Server/backend
python manage.py check
python -m pytest estimation/tests -q
cd ../dashboard
npm test -- --run
npm run build
cd ../../
python -m pytest MPC/tests -q
```

Backend DB checks require MySQL/XAMPP to be running with the configured database credentials.

## Standalone Deploy

`Server/` can be deployed without copying the full monorepo when its runtime inputs are supplied explicitly:

- Install backend dependencies with `Server/backend/requirements.txt`.
- Provide `greenhouse-kalman==0.1.0` and `greenhouse-mpc==0.1.0` through a private package index or a wheelhouse.
- Put the trained ARX artifact at `Server/backend/artifacts/arx_model.json`, or set `ARX_MODEL_PATH` to another absolute path.

For monorepo development, keep using `requirements-local.txt`; it installs `../../Kalman` and `../../MPC` as editable local packages.
