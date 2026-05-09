# Plan: Finish Green-House Server Cutover

## Goal

Make `Green-House/` the only runtime server so the old `Server/` folder can be removed after review.

This is a production-scope local migration, not a UI redesign. Green-House keeps its current frontend/API style, but it must own the backend workflow that used to live in `Server/`:

- authenticated user ownership
- user -> greenhouse -> config/state/recommendation scoping
- Kalman estimation from live sensor data
- AMPC recommendation from the latest valid estimation
- compatibility endpoints needed by the old Server API
- no runtime dependency on `pipeline_cycles`

## Required Fixes

### 1. Port the missing Server API surface

Green-House must expose compatible endpoints for:

- `GET /api/runs/`
- `GET /api/runs/<run_id>/series/`
- `GET /api/runs/<run_id>/metrics/`
- `GET/PATCH /api/greenhouses/<greenhouse_id>/control-profile/`
- `POST /api/greenhouses/<greenhouse_id>/ampc/recommendations/`
- `GET /api/greenhouses/<greenhouse_id>/ampc/recommendations/latest/`
- `POST /api/ingest/samples/`

The endpoints must enforce authenticated ownership for user-facing greenhouse routes.

### 2. Make `api_estimationcycle` the runtime source of truth

`api_estimationcycle` replaces legacy `pipeline_cycles`.

- Runtime AMPC reads only `api_estimationcycle`.
- Live ingest writes `api_estimationcycle`.
- Existing copied rows remain available through Green-House APIs.
- Drop or retire `pipeline_cycles` after verifying copied data exists in `api_estimationcycle`.
- Do not keep a dual-read path from both tables.

### 3. Add production multi-greenhouse domain model

Green-House must support:

- user owns many greenhouses
- greenhouse has control profile
- greenhouse has live runs
- greenhouse has sensor data / estimation cycles
- greenhouse has AMPC recommendations
- AMPC service validates requested greenhouse belongs to authenticated user

The singleton `ControlProfile` pattern can remain only as legacy/default fallback for existing UI routes; new production paths must be greenhouse-scoped.

### 4. Keep Kalman and MPC integration working

The Green-House backend must continue to:

- import `kalman` from `Kalman/`
- import `mpc` from `MPC/`
- load default ARX artifact from settings
- run validation/preprocessing/ARX/Kalman on ingest
- run AMPC with fail-closed behavior
- never execute unsafe actuator commands

### 5. Update docs that would become stale after deleting `Server/`

Update references so future agents/users know:

- Green-House is the server integration point
- Kalman is the algorithm package
- MPC is the controller package
- backend README only lists real endpoints

## Implementation Tasks

1. Add Green-House database models and migrations:
   - `Greenhouse`
   - `ExperimentRun`
   - `ExperimentConfig`
   - `EvaluationSummary`
   - `GreenhouseControlProfile`
   - greenhouse/run links for sensor, estimation, recommendation records

2. Add data migration:
   - create a default greenhouse if needed
   - create or reuse a live run
   - attach existing readings/estimations/recommendations to the default greenhouse
   - copy singleton profile values into greenhouse control profile
   - verify `api_estimationcycle` has the copied legacy rows before dropping `pipeline_cycles`

3. Add compatibility serializers and endpoints for the old Server API.

4. Refactor AMPC service to accept `user + greenhouse_id` and filter all state/history/recommendations by greenhouse.

5. Refactor ingest service so `/api/ingest/samples/` maps a live sample into Green-House sensor data and `api_estimationcycle`.

6. Update docs:
   - `Kalman/README.md`
   - `MPC/README.md`
   - `Green-House/backend/README.md`

## Validation

Run:

```powershell
cd Green-House\backend
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py check
python -m pytest api\tests -q
```

Run package checks:

```powershell
python -m pytest Kalman\tests -q
python -m pytest MPC\tests -q
```

Run frontend check:

```powershell
cd Green-House\frontend
npm run build
```

Smoke test:

- login as a user
- create or verify a greenhouse owned by that user
- ingest one sample through `/api/ingest/samples/`
- verify `api_estimationcycle` receives the cycle
- call greenhouse AMPC recommendation endpoint
- verify unsafe recommendations do not create dangerous actuator commands

## Delete Criteria For `Server/`

Only delete `Server/` after:

- Green-House compatibility endpoints pass smoke tests
- docs no longer point to `Server/` as the active integration
- no Green-House runtime code imports from `Server/`
- owner review accepts the cutover
