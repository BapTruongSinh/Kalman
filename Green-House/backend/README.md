
## 2. Cấu hình môi trường
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-local.txt
Copy-Item .env.example .env
```

`requirements-local.txt` installs the Django backend plus editable local packages from `../../Kalman` and `../../MPC`. Use `requirements.txt` only for the base Django dependencies.

## 3. Khởi tạo project
```powershell
python manage.py makemigrations api
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## 4. API chính cho frontend
- `POST /api/auth/login/`
- `GET /api/dashboard/overview/`
- `GET /api/sensor-readings/latest/`
- `GET /api/sensor-readings/chart/?metric=temperature&hours=24`
- `GET /api/devices/`
- `POST /api/devices/{id}/toggle/`
- `POST /api/devices/{id}/command/`
- `GET /api/alerts/`
- `POST /api/alerts/{id}/mark_read/`
- `POST /api/alerts/mark_all_read/`
- `GET /api/forecast/`
- `GET /api/auto-settings/`
- `PATCH /api/auto-settings/`
- `POST /api/control/auto-recommendation/`

## 5. API compatibility Server cu
- `GET /api/runs/`
- `GET /api/runs/{run_id}/series/`
- `GET /api/runs/{run_id}/metrics/`
- `GET /api/greenhouses/{greenhouse_id}/control-profile/`
- `PATCH /api/greenhouses/{greenhouse_id}/control-profile/`
- `POST /api/greenhouses/{greenhouse_id}/ampc/recommendations/`
- `GET /api/greenhouses/{greenhouse_id}/ampc/recommendations/latest/`
- `POST /api/ingest/samples/`

## 6. API cho ESP32
Header bắt buộc:
```http
X-Device-Token: esp32-local-token
```

### Gửi dữ liệu cảm biến
```http
POST /api/ingest/readings/
Content-Type: application/json
```

Body mẫu:
```json
{
  "temperature": 29.5,
  "humidity": 71.2,
  "light": 18250,
  "soil_moisture": 43.0,
  "device_states": {
    "fan_on": false,
    "pump_on": false,
    "light_on": true
  },
  "firmware_version": "1.0.0"
}
```

### Heartbeat
```http
POST /api/ingest/heartbeat/
```

### Lấy lệnh đang chờ
```http
GET /api/ingest/commands/pending/
```

### ACK lệnh
```http
POST /api/ingest/commands/{id}/ack/
```

Body mẫu:
```json
{
  "status": "ack",
  "actual_state": true
}
```
