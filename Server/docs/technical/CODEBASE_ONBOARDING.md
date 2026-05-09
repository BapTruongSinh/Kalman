# Codebase Onboarding

> Scope: repo `demo_kalman/`, gồm `ARX/` và `Kalman/`
> Mục tiêu: giúp người mới hiểu luồng dữ liệu, module chính, và các invariant trước khi sửa code
> Last updated: 2026-05-08

## 1. Repo Này Đang Làm Gì

Repo có hai miền liên kết:

- `ARX/` là miền nghiên cứu/mô hình hóa. Nó sinh hoặc phân tích dữ liệu greenhouse, train/đánh giá ARX bên ngoài app, và xuất artifact chuẩn `ARX/arx_model.json`.
- `Kalman/` là ứng dụng chính. Runtime hiện tại là live-only: nhận sample sensor realtime, validate, preprocess theo live skip policy, dùng artifact ARX làm prior, chạy Adaptive Kalman một bước, lưu MySQL, đánh giá online, và hiển thị dashboard.

Điểm quan trọng: Django app không còn replay offline, không train ARX trong app, không dùng SQLite override, không giữ split train/validation/test trong runtime. `ARX/` là source artifact/nghiên cứu và được giữ read-only trừ khi user yêu cầu rõ.

## 2. Bức Tranh Kiến Trúc

Luồng chính:

```text
Device POST /api/ingest/samples/
  -> token auth + owner/status check
  -> RawRecord
  -> validate_live_record()
  -> preprocess_single()
  -> cached ARXPredictionAdapter.load_artifact(settings.ARX_MODEL_PATH)
  -> AdaptiveKalmanCycle.step()
  -> PipelineCycle in MySQL
  -> EvaluationSummary online
  -> Dashboard online chart + metrics
```

Các lớp chính:

- `ARX modeling layer`: tạo và đánh giá model ARX, xuất `arx_model.json`.
- `Live ingestion layer`: nhận payload API và chuẩn hóa thành `RawRecord`.
- `Validation/preprocessing layer`: live-only, chỉ `validate_live_record()` và `preprocess_single()`; invalid sample thành effective `None` để Kalman skip measurement update.
- `Prediction layer`: `ARXPredictionAdapter` load artifact có sẵn, `predict()` không raise, trả `PredictionResult`.
- `Estimator layer`: `AdaptiveKalmanCycle` chạy từng sample, dùng ARX prior nếu đủ history, cập nhật `R` theo innovation.
- `Persistence layer`: `PipelineCycle` là trace từng bước; `ExperimentRun`/`ExperimentConfig` lưu run và config; `EvaluationSummary` lưu metric online.
- `API layer`: dashboard GET APIs và live ingest POST API.
- `Frontend layer`: Vite/React dashboard chỉ đọc online series/metrics.

## 3. Thứ Tự Đọc Repo

1. `Kalman/docs/technical/ARCHITECTURE.md`: kiến trúc live-only hiện tại.
2. `Kalman/docs/technical/DATABASE.md`: schema ORM và constraint hiện tại.
3. `Kalman/backend/estimation/models.py`: source of truth của schema runtime.
4. `Kalman/backend/estimation/api/ingest.py`: live path end-to-end.
5. `Kalman/backend/estimation/kalman/cycle.py`: logic Adaptive Kalman.
6. `Kalman/backend/estimation/prediction/arx_adapter.py`: runtime ARX artifact adapter.
7. `Kalman/dashboard/src/components/RunDashboard.tsx`: dashboard online-only.
8. `Kalman/docs/technical/AMPC_MODELING_HANDOFF.md`: handoff cho MPC sau v1.

## 4. ARX/

`ARX/` trả lời câu hỏi: predictor nền đã đủ dùng chưa?

Các file cần biết:

- `ARX/data_generator.py`: sinh dữ liệu greenhouse synthetic có mùa vụ, actuator logic, hysteresis, persistent excitation.
- `ARX/arx_pipeline.py`: train/evaluate/export ARX artifact.
- `ARX/arx_model.json`: artifact runtime mà Django app load qua `settings.ARX_MODEL_PATH`.
- `ARX/arx_reporting.py`: phân tích/report ngoài runtime app.

Không kéo training/reporting code vào Django nếu không có yêu cầu riêng. Runtime chỉ cần artifact đã có.

## 5. Backend Kalman/

### 5.1 Settings

- `Kalman/backend/config/settings.py` cấu hình Django, DRF, CORS, MySQL, token auth, `ARX_MODEL_PATH`.
- DB mặc định là MySQL/XAMPP. Không còn SQLite override.
- `ARX_MODEL_PATH` mặc định trỏ tới repo-root `ARX/arx_model.json`.

### 5.2 Models

`Kalman/backend/estimation/models.py` là schema source of truth:

- `ExperimentRun`: chỉ `run_type="live"`; DB có check constraint chặn legacy `offline_replay`.
- `ExperimentConfig`: chỉ giữ config Kalman và `raw_config_json`; không còn `preprocessing_policy`, split ratio, hoặc ARX train config.
- `PipelineCycle`: bảng lõi từng cycle. Chỉ `slice_type="online"`, `source_type="live"`, `cycle_status` gồm `ok`, `skipped_no_measurement`, `error`.
- `EvaluationSummary`: metric tổng hợp cho online segment.

Invariant quan trọng:

- `ingest_dedupe_key = live|{run_id}|{UTC sample_ts}`.
- Unique theo `(run, cycle_index)` và `(run, ingest_dedupe_key)`.
- Duplicate `(run_id, sample_ts)` trong migration chỉ được auto-delete nếu payload raw giống hệt và duplicate nằm ở tail run; nếu không migration phải fail-fast.

### 5.3 Ingestion

`estimation/ingestion/` hiện là live-only:

- `loader.py`: chỉ định nghĩa `RawRecord`.
- `validator.py`: chỉ `validate_live_record()`; `soil_moisture` là measurement chính, ancillary channels có thể thiếu nhưng nếu có phải finite và trong range.
- `preprocessor.py`: chỉ `preprocess_single()`; valid sample pass-through, invalid sample thành `preprocess_status="skipped"` và effective values `None`.

Không còn `load_csv()`, `validate_batch()`, `validate_record()`, `keep_last`, hoặc `interpolate` trong runtime app.

### 5.4 Prediction

`estimation/prediction/` giữ contract predictor thay thế được:

- `PredictionAdapter`: interface runtime gồm `predict()` và `load_artifact()`.
- `ARXPredictionAdapter`: load artifact từ `ARX/arx_model.json`, đọc metadata order/input columns, predict one-step soil moisture.
- `predict()` không raise; lỗi đi qua `PredictionResult.status`.

App không còn `train()` hoặc `save_artifact()` cho ARX.

### 5.5 Adaptive Kalman

`estimation/kalman/cycle.py` là estimator runtime:

- State scalar: `Soil_Moisture`.
- `AdaptiveKalmanCycle.step()` không raise.
- Prior lấy từ ARX nếu adapter có đủ history, nếu không fallback carry-forward posterior.
- Nếu measurement valid: tính innovation, adaptive `R`, gain `K`, posterior.
- Nếu measurement absent/skipped: posterior = prior, `adaptive_status="R_skipped"`, `cycle_status="skipped_no_measurement"`.
- Nếu lỗi nội bộ: trả `cycle_status="error"` và giữ state tốt gần nhất.

### 5.6 Pipeline Store

`estimation/pipeline/store.py`:

- `ingest_dedupe_key_for_persist()` tạo key live theo UTC timestamp.
- `map_result_to_cycle()` map `CycleResult` sang `PipelineCycle`.
- `begin_run()` và `end_run()` chuyển trạng thái run bằng update có điều kiện.

### 5.7 Evaluation

`estimation/evaluation/`:

- `metrics.py`: pure metrics, không phụ thuộc Django.
- `reporter.py`: `evaluate_slice(run_pk, "online")`, `evaluate_online(run_pk)`, report/export.
- Metric chính: RMSE/MAE ARX vs filtered, variance reduction, latency, innovation, adaptive `R`, covariance, acceptance flags.

### 5.8 API

Endpoints:

- `GET /api/runs/`
- `GET /api/runs/{id}/series/?slice=online&limit=...&stride=...`
- `GET /api/runs/{id}/metrics/`
- `POST /api/ingest/samples/`

Dashboard GET API có thể dùng trong dev. Live ingest POST bắt buộc token auth và owner đúng run.

## 6. Dashboard

Dashboard nằm ở `Kalman/dashboard/`:

- `src/api/client.ts`: fetch helpers.
- `src/api/types.ts`: TypeScript contract với backend.
- `src/components/RunSelector.tsx`: chọn run.
- `src/components/RunDashboard.tsx`: online-only; request `slice=online`, stride, limit; render chart + status + metrics.
- `src/components/SliceChart.tsx`: raw / ARX / Kalman filtered.
- `src/components/AdaptiveStatusBar.tsx`: phân bố `R_updated`, `R_skipped`, `skipped`.
- `src/components/MetricsPanel.tsx`: metric online và acceptance gate.

Không còn UI cho `all/train/validation/test`.

## 7. AMPC / MPC Boundary

v1 chưa có MPC solver hoặc autonomous actuator scheduler. Repo đã có handoff cho MPC:

- `AMPC_MODELING_HANDOFF.md`: state/control/disturbance/cost/safety.
- State đầu tiên: soil moisture `theta` từ Kalman posterior.
- Control candidates: `Drip`, `Mist`, `Fan`.
- Disturbances available now: `Temperature`, `Humidity`, `Light`.
- Planned physical variables: `Dr`, ET0/ETc, soil/crop calibration.
- Cost candidates: moisture zone tracking, water, energy, switching, delta-u smoothing.
- Safety candidates: soil moisture bounds, RH cap, daily water cap, mist/night rules, sensor fault fallback.

Hiện có đủ để thiết kế controller boundary và prototype nghiên cứu. Chưa đủ để deploy MPC thật nếu thiếu plant/water calibration, actuator limits, ET/weather feed, setpoint schedule, horizon/weights, và hardware safety policy.

## 8. Những Điểm Dễ Nhầm

- `ARX/` là nghiên cứu/artifact, không phải runtime training trong Django.
- `Kalman/` runtime hiện live-only.
- `PipelineCycle` là nguồn dữ liệu cho cả dashboard và evaluation; đổi enum/field phải kiểm API, frontend, tests, migrations.
- `AdaptiveKalmanCycle.step()` phải không raise.
- Invalid live measurement không còn keep-last/interpolate; chỉ skip measurement update.
- `run_type`, `slice_type`, `source_type`, `cycle_status`, `preprocess_status` đều có DB constraints; đừng bypass service để ghi enum rác.
- `CODEBASE_ONBOARDING.md` chỉ cập nhật sau khi user review OK.

## 9. Test Và Validation Gates

Backend:

```powershell
cd Kalman/backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python -m pytest estimation\tests -q
```

Dashboard:

```powershell
cd Kalman/dashboard
npm test -- --run
npm run build
```

Grep hữu ích sau live-only cleanup:

```powershell
rg -n "offline_replay|csv_replay|mysql_replay|load_csv|validate_batch|validate_record|skipped_invalid" Kalman\backend\estimation -g "*.py" -g "!**/migrations/**"
rg -n "offline_replay|slice=train|slice=test|train|validation" Kalman\dashboard\src -g "*.ts" -g "*.tsx"
```

## 10. File Map Ngắn Gọn

- `Kalman/backend/config/settings.py`: settings Django/MySQL/ARX artifact path.
- `Kalman/backend/estimation/models.py`: schema ORM live-only.
- `Kalman/backend/estimation/api/ingest.py`: live ingest end-to-end.
- `Kalman/backend/estimation/api/views.py`: dashboard APIs.
- `Kalman/backend/estimation/ingestion/*.py`: `RawRecord`, live validation, live preprocessing.
- `Kalman/backend/estimation/prediction/arx_adapter.py`: ARX artifact runtime adapter.
- `Kalman/backend/estimation/kalman/cycle.py`: Adaptive Kalman one-step estimator.
- `Kalman/backend/estimation/pipeline/store.py`: mapping/persist/run lifecycle.
- `Kalman/backend/estimation/evaluation/*.py`: metric/report/export online.
- `Kalman/dashboard/src/components/*.tsx`: dashboard UI.
- `Kalman/docs/technical/AMPC_MODELING_HANDOFF.md`: MPC handoff.
