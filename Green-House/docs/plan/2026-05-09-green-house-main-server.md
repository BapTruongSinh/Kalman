# Plan: Green-House As Main Local Server

## Goal

`Green-House/` is the main local app. `Server/` remains only as reference. The Green-House backend keeps its existing auth, dashboard, sensor, device, alert, and ingest API while adding Kalman estimation and AMPC control backed by `ARX/arx_model.json`.

## Scope

- Add local package dependencies for `Kalman` and `MPC`.
- Add `ARX_MODEL_PATH`, defaulting to repo root `ARX/arx_model.json`.
- Persist Kalman estimation cycles for each ingested `SensorData`.
- Persist AMPC recommendations and actuator command audit.
- Add a singleton control profile for crop/controller settings.
- Add API endpoints:
  - `GET /api/forecast/`
  - `GET /api/auto-settings/`
  - `PATCH /api/auto-settings/`
  - `POST /api/control/auto-recommendation/`
- Wire existing Green-House frontend pages to the new APIs without replacing the UI with the old `Server/dashboard`.

## Runtime Flow

1. ESP32 posts `POST /api/ingest/readings/`.
2. Backend saves `SensorData`.
3. Backend validates/preprocesses the reading through `kalman.ingestion`.
4. Backend loads the default ARX artifact and runs `AdaptiveKalmanCycle`.
5. Backend saves `EstimationCycle`.
6. If control mode is `AUTO`, backend runs AMPC using latest estimation/history and `ControlProfile`.
7. Backend saves `AMPCRecommendation`.
8. If recommendation is safe and `ControlProfile.actuator_enabled=true`, backend queues a `DeviceCommand` for the pump.

## Validation

- Backend:
  - `cd Green-House/backend`
  - `python manage.py makemigrations api`
  - `python manage.py migrate`
  - `python manage.py check`
- Packages:
  - `python -m pytest Kalman/tests -q`
  - `python -m pytest MPC/tests -q`
- Frontend:
  - `cd Green-House/frontend`
  - `npm run build`

## Notes

- This task is local-only. Internet deployment/runbook is separate.
- `Server/` is not deleted in this task.
- Green-House currently remains single-zone/single-greenhouse. Multi-greenhouse ownership is a required production direction, but it is not part of this local migration task.
