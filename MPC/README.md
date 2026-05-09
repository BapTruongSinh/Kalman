# MPC

> Controller project cho smart greenhouse: v2 MPC khuyến nghị lệnh bơm nước, v3 AMPC thêm bias adaptation và closed-loop pilot có fail-safe.

---

## Overview

`MPC/` là project độc lập ở repo root, được tạo để phát triển controller sau khi `Kalman/` đã có live-only estimator. V2 nhận state độ ẩm đất từ Kalman posterior hoặc raw sensor fallback, dùng ARX artifact làm plant model, rồi xuất recommendation `pump_seconds`.

V3 mở rộng thành Adaptive MPC bằng cách bù bias dự báo từ sai số gần đây. Closed-loop pilot chỉ được bật khi cấu hình actuator hợp lệ; fail-safe mặc định là tắt bơm và ghi cảnh báo khi input stale, solver lỗi, model lỗi, hoặc actuator API lỗi.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Controller core | Python | Package import được và CLI |
| Model source | `../ARX/arx_model.json` | Reuse ARX artifact, không train trong MPC |
| State source | Kalman posterior / raw sensor fallback | If payload includes `kf_R > 15`, MPC treats posterior as untrusted and falls back to raw sensor |
| Solver | Beam-grid shooting | Không thêm SciPy/CVXPY ở v2 |
| Simulation | CSV + JSON report | So sánh MPC với threshold baseline |
| Actuator pilot | HTTP POST + Bearer token | Chỉ ở v3, config/env driven |
| Tests | pytest | Unit + CLI smoke + safety tests |

---

## Project Structure

```text
MPC/
  mpc/
    cli.py
    config.py
    schema.py
    state.py
    types.py
    plant/
    solver/
    simulation/
    adaptive/
    actuator/
    closed_loop.py
  tests/
  PRD.md
  TODO.md
  CLAUDE.md
  README.md
  .tasks/
  docs/
```

---

## CLI

Chạy từ thư mục `MPC/`:

```powershell
cd MPC
python -m mpc recommend
python -m mpc simulate --max-steps 288
python -m mpc adaptive-simulate --max-steps 288
python -m mpc auto
python -m mpc config-schema
```

Khi bỏ trống path, CLI dùng demo defaults: `..\ARX\arx_model.json`, `examples\demo_state.json`, `..\ARX\greenhouse_data.csv`, và ghi vào `reports\`. Các tham số như `--artifact`, `--state-json`, `--input`, `--output`, `--config`, `--beam-width`, `--max-steps` vẫn override được khi cần test/dev.

`auto` là lệnh runtime ngắn cho closed-loop. Lệnh này chỉ POST actuator khi config explicit hợp lệ. Nếu thiếu URL/token/env hoặc HTTP lỗi, output là fail-closed command `pump_seconds=0.0`.

`config-schema` xuất JSON gồm default controller config, default runtime path, nhóm field người dùng nên nhập, và nhóm field hệ thống có thể giữ mặc định để website load lên form.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MPC_ACTUATOR_TOKEN` | v3 only | Bearer token gửi actuator command; tên biến này do `actuator.bearer_token_env` trong config chỉ định |
| `MPC_CONFIG_PATH` | No | Đường dẫn config override nếu không truyền `--config` |

---

## Tests

```powershell
python -m pytest MPC/tests -q
python -m compileall -q MPC/mpc
```

Validation gate chi tiết nằm trong [`docs/technical/VALIDATION.md`](docs/technical/VALIDATION.md).

---

## Status

Current: task #010 simplified CLI defaults and added config schema export for website-facing configuration.

Core runtime bắt đầu từ task #002; solver/recommendation đã có ở task #003; CLI/simulation đã có ở task #004; v2 validation suite đã có ở task #005; v3 adaptive simulation đã có ở task #006; closed-loop HTTP pilot đã có ở task #007; demo/validation docs đã được đồng bộ ở task #008; objective cost đã normalize đúng ở task #009; CLI/schema default đã có ở task #010.
