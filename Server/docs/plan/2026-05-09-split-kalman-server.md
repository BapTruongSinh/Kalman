# Plan: Tach Kalman thanh package thuat toan va tao Server rieng

## Muc tieu

Tach repo thanh cac boundary ro rang:

```text
ARX/      -> research, train/export artifact ARX
Kalman/   -> package thuat toan Adaptive Kalman, import name: kalman
MPC/      -> package thuat toan MPC/AMPC controller
Server/   -> Django backend + dashboard + DB/API/auth/business workflow
```

`Kalman/` khong con chua Django, DB models, migrations, API, dashboard. `Server/` la noi chay `python manage.py runserver`, nhan sensor, luu DB, goi package `kalman` va `mpc`.

## Thay doi chinh

- Chuyen app hien tai ra `Server/`:
  - `Server/backend` -> `Server/backend`
  - `Server/dashboard` -> `Server/dashboard`
  - docs/TODO/task history cua app -> `Server/`
  - giu Django app label `estimation` de khong doi migration/table name.
- Bien `Kalman/` thanh package Python doc lap:
  - them `Kalman/pyproject.toml`
  - tao package import `Kalman/kalman/`
  - dua pure algorithm vao package: ingestion contract, validation, preprocessing, prediction adapter, ARX adapter, Adaptive Kalman filter, pure metrics, pure run config dataclass.
  - cam import Django/ORM/DRF/settings/DB trong `Kalman/kalman`.
- Cap nhat `Server/backend`:
  - `requirements.txt` them `-e ../../Kalman` va giu `-e ../../MPC`
  - live ingest import tu `kalman.*`
  - persistence/API/AMPC van o `Server/backend/estimation`.
- Khong doi endpoint, DB schema, table name, hay behavior.

## Validation

- `python -m pytest Kalman/tests -q`
- `python -m compileall -q Kalman/kalman`
- `cd Server/backend; python manage.py check`
- `cd Server/backend; python manage.py makemigrations --check --dry-run`
- `cd Server/backend; python manage.py migrate --check`
- `cd Server/backend; python -m pytest estimation/tests -q`
- `cd Server/backend; python -m compileall -q estimation config`
- `cd Server/dashboard; npm test -- --run`
- `cd Server/dashboard; npm run build`
- `python -m pytest MPC/tests -q`
- Grep de dam bao `Kalman/kalman` khong import Django/DRF/ORM/settings.

