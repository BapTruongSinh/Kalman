# Plan: Dọn Runtime Online Với ARX Artifact

## Approach

Chuyển runtime về một hướng duy nhất: live/online ingestion sử dụng artifact có sẵn `../ARX/arx_model.json` để dự đoán, không replay offline và không train ARX trong app. Trước khi xóa code, chạy `understand` để có bản đồ phụ thuộc, sau đó dùng `understand-explain` cho các module nóng để tránh xóa nhầm contract live path vẫn cần.

## Scope

- In:
  - Dùng `C:\Users\ADMIN\.agents\skills\understand` để tạo/cập nhật `.understand-anything/knowledge-graph.json` cho `Kalman/`.
  - Dùng `C:\Users\ADMIN\.agents\skills\understand-explain` cho `estimation/prediction/arx_adapter.py`, `estimation/kalman/cycle.py`, `estimation/api/ingest.py`, `estimation/run_config/config.py`, `estimation/models.py`, và test liên quan.
  - Refactor ARX adapter thành artifact-only runtime loader đọc từ `../ARX/arx_model.json`.
  - Nối live ingest với ARX adapter đã load, để Kalman dùng ARX prediction làm prior thay vì fallback mặc định.
  - Xóa hoặc thu hẹp offline replay path, split/retrain config, self-training code, tests và docs không còn dùng.
  - Đồng bộ docs/task note sau khi code thay đổi, trừ `CODEBASE_ONBOARDING.md` chỉ cập nhật sau khi user review OK.

- Out:
  - Không sửa `ARX/arx_model.json` và không sửa logic nghiên cứu trong `ARX/` nếu không có yêu cầu riêng.
  - Không thêm model registry, automatic retraining, LightGBM/XGBoost, AMPC controller, hoặc closed-loop actuation.
  - Không thay đổi `PRD.md` nếu user chưa yêu cầu cập nhật requirement chính thức.

## Action Items

- [x] Run `understand` cho `Kalman/` và xác nhận graph tạo được; nếu plugin thiếu dependency thì ghi rõ blocker và tiếp tục bằng static grep/read.
  - Result: blocker. `pnpm` is not installed and `C:\Users\ADMIN\.understand-anything-plugin\packages\core\dist\index.js` is missing, so no `.understand-anything/knowledge-graph.json` could be generated. Continued with static `rg`/read audit.
- [x] Use `understand-explain` trên các module target để lập danh sách dependency cần giữ/xóa: `arx_adapter.py`, `base.py`, `cycle.py`, `ingest.py`, `run_config/config.py`, `models.py`, `pipeline/store.py`, tests.
  - Result: blocker from missing graph above. Dependency audit completed manually for the target modules and related tests.
- [x] Audit references bằng `rg` cho `offline_replay`, `csv_replay`, `mysql_replay`, `replay(`, `split_chronological`, `train_ratio`, `ARXTrainConfig`, `train(`, `save_artifact`, `greenhouse_data.csv`, và `evaluate_all_slices`.
- [x] Refactor `estimation.prediction` contract nếu cần: giữ `predict()` + `load_artifact()`, bỏ yêu cầu runtime `train()` / `save_artifact()` khỏi live app path; nếu abstract base đang ép train/save, tách thành optional/offline-only interface hoặc xóa abstract method không còn dùng.
  - Result: `PredictionAdapter` now requires only runtime prediction/artifact behavior. `ARXPredictionAdapter` no longer exposes app-side `train()` or native `save_artifact()`.
- [x] Refactor `ARXPredictionAdapter` thành artifact-only adapter: load `Path(settings.ARX_MODEL_PATH)` mặc định trỏ tới `../ARX/arx_model.json`, giữ parser pipeline format, xóa OLS train/save native artifact nếu không còn caller hợp lệ.
  - Result: app runtime loads through `settings.ARX_MODEL_PATH`; app-side OLS `train()` and native `save_artifact()` were removed from `ARXPredictionAdapter`.
- [x] Update live ingest để khởi tạo/cached ARX adapter từ `arx_model.json`, duy trì history theo run, và truyền adapter vào `AdaptiveKalmanCycle` để mỗi sample online có ARX prior khi đủ history.
- [x] Remove offline replay code surface: `AdaptiveKalmanCycle.replay()` nếu chỉ dùng cho replay batch, CSV split-only helpers nếu không còn được live/tests cần, `RunType.OFFLINE_REPLAY`, replay source enum, replay dedupe logic, và config train/val/test ratio theo mức độ migration/test cho phép.
  - Result: removed from app code. Migration `0006_live_only_cleanup` normalizes old rows to `live` / `online`, drops `ARXArtifact`, and removes split/train config fields.
- [x] Fix live-only review findings: backfill migrated `ingest_dedupe_key` values to `live|run_id|UTC sample_ts`, delete duplicate `(run, sample_ts)` rows before enforcing that invariant, add DB/service guard so `offline_replay` cannot be created, and remove dead `preprocessing_policy` / batch keep-last/interpolate surface.
- [x] Update or delete tests: bỏ tests train/replay/self-save; giữ tests load `ARX/arx_model.json`, predict never-raises, live ingest with ARX prior, idempotency, Kalman one-step, store mapping, API dashboard compatibility.
  - Result: train/replay/self-save tests were replaced with live-only coverage. MySQL pytest passes.
- [x] Update docs/tasks sau code: `ARCHITECTURE.md`, `DECISIONS.md` bằng ADR mới supersede ADR-003, `API.md`, `USER_GUIDE.md`, `METHODOLOGY_V1.md`, `DATABASE.md` nếu schema enum/field đổi, `TODO.md` và `.tasks/` nếu tạo task mới.
  - Result: docs updated; no TODO/.tasks change needed because this was a plan file, not a numbered task. `CODEBASE_ONBOARDING.md` intentionally not updated until user review approval.
- [x] Validate: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, targeted pytest (`test_prediction.py`, `test_live_ingest.py`, `test_kalman.py`, `test_pipeline_store.py`, `test_api.py`), sau đó full backend pytest nếu thời gian cho phép.

## Validation Gates

- Logic: chỉ còn một runtime path chính là live/online ingestion; ARX prediction lấy từ artifact có sẵn, không còn train mới trong app.
- Business: model source là `../ARX/arx_model.json`, đúng yêu cầu owner; v2-ready vì code bớt offline/retrain noise.
- Security: live ingest vẫn bắt buộc token/auth/owner, không lộ path tùy ý từ request; model path lấy từ settings/env hợp lệ.
- Tests: live ingest với artifact ARX pass, prediction artifact pass, Django checks pass, migration check không drift.

## Open Questions

- `understand`/`understand-explain`: plugin core was rebuilt with `pnpm --filter @understand-anything/core build`, but Codex terminal has no subagent dispatcher for the full graph phases, so static audit was used for code cleanup.
- `../ARX/arx_model.json` is treated as the standard artifact and `ARX/` remains read-only.
- Offline replay/train helpers are no longer retained in application code.
