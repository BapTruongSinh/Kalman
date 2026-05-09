# Green-House Codebase Onboarding

> Scope: `Green-House/` is the active Django + dashboard server app.
> Last updated: 2026-05-09.

## Runtime Boundary

- `ARX/` owns research/training/export and provides `ARX/arx_model.json`.
- `Kalman/` is a pure algorithm package imported as `kalman`.
- `MPC/` is a pure controller package imported as `mpc`.
- `Green-House/` owns Django, auth, database, ingest APIs, dashboard APIs, AMPC orchestration, and frontend.
- `Server/` is legacy reference only and must not be required by runtime or preflight.

## Main Flow

```text
ESP32 or live sample API
  -> Green-House/backend/api views/services
  -> SensorData
  -> kalman validation + preprocessing + ARX prior
  -> api_estimationcycle
  -> mpc AMPC recommendation
  -> api_ampcrecommendation
  -> dashboard JSON and optional DeviceCommand when AUTO + safe
```

## Required Read Order

1. `Green-House/README.md`
2. `Green-House/backend/README.md`
3. `Green-House/backend/api/models.py`
4. `Green-House/backend/api/estimation.py`
5. `Green-House/backend/api/ampc.py`
6. `Green-House/backend/api/views.py`
7. `Green-House/backend/api/tests/test_server_cutover.py`
8. `MPC/docs/technical/API.md`
9. `MPC/docs/technical/VALIDATION.md`

## Important Invariants

- `api_estimationcycle` is the runtime source of truth. Do not reintroduce `pipeline_cycles`.
- Default ARX artifact path resolves from `Green-House/backend/config/settings.py` to repo-root `ARX/arx_model.json`.
- Local backend install uses `Green-House/backend/requirements-local.txt`, which installs `../../Kalman` and `../../MPC`.
- User-facing AMPC endpoints must verify user ownership through `Greenhouse.owner`.
- Unsafe AMPC results must fail closed and must not create dangerous actuator commands.
- Actuator auto-send is allowed only when control mode is `AUTO`, profile actuator is enabled, and recommendation safety is `safe`.

## Validation Gates

Run from repo root unless noted:

```powershell
cd Green-House\backend
python manage.py test api
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pip install -r requirements-local.txt --dry-run
```

```powershell
cd Green-House\frontend
npm test
npm run build
```

```powershell
python -m pytest Kalman\tests -q
python -m pytest MPC\tests -q
```
