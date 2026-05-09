# Green-House Local Server

`Green-House/` is the main local app.

## Backend

Install local dependencies from `Green-House/backend`:

```powershell
python -m pip install -r requirements-local.txt
```

Create/update the backend database:

```powershell
python manage.py migrate
python manage.py check
python manage.py runserver
```

Default ARX artifact path:

```text
../../ARX/arx_model.json
```

Override with `ARX_MODEL_PATH` in `backend/.env` if needed.

## Frontend

From `Green-House/frontend`:

```powershell
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`.

## AMPC Endpoints

- `GET /api/forecast/`
- `GET /api/auto-settings/`
- `PATCH /api/auto-settings/`
- `POST /api/control/auto-recommendation/`
- `GET /api/runs/`
- `GET /api/runs/{run_id}/series/`
- `GET /api/runs/{run_id}/metrics/`
- `GET/PATCH /api/greenhouses/{greenhouse_id}/control-profile/`
- `POST /api/greenhouses/{greenhouse_id}/ampc/recommendations/`
- `GET /api/greenhouses/{greenhouse_id}/ampc/recommendations/latest/`

ESP32 ingest stays at `POST /api/ingest/readings/` with `X-Device-Token`.
Legacy live ingest compatibility is available at `POST /api/ingest/samples/`.
