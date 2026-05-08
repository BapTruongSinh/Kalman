# MPC

> Controller project cho smart greenhouse: v2 MPC khuyến nghị lệnh bơm nước, v3 AMPC thêm bias adaptation và closed-loop pilot có fail-safe.

---

## Overview

`MPC/` là project độc lập ở repo root, được tạo để phát triển controller sau khi `Kalman/` đã có live-only estimator. V2 tập trung vào MPC một đầu vào cho bơm nước: nhận state độ ẩm đất từ Kalman posterior hoặc raw sensor fallback, dùng ARX artifact làm plant model, rồi xuất recommendation `pump_seconds`.

V3 mở rộng thành Adaptive MPC bằng cách bù bias dự báo từ sai số gần đây. Closed-loop pilot chỉ được bật khi cấu hình actuator hợp lệ; fail-safe mặc định là tắt bơm và ghi cảnh báo khi input stale, solver lỗi, model lỗi, hoặc actuator API lỗi.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Controller core | Python | Package import được và CLI |
| Model source | `../ARX/arx_model.json` | Reuse ARX artifact, không train trong MPC v2 |
| State source | Kalman posterior / raw sensor fallback | Đọc từ file/state payload trước; DB/API integration để task sau |
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
    state.py
    types.py
    plant/
      arx.py
    solver/
      cost.py
      grid.py
    simulation/
      baseline.py
      report.py
      runner.py
  tests/
  PRD.md
  TODO.md
  CLAUDE.md
  README.md
  .tasks/
  docs/
    technical/
    user/
    content/
    plan/
```

Task #001 đã chốt package architecture và config contract. Task #002 đã tạo config/state contracts và ARX plant adapter. Task #003 đã tạo recommendation output, cost scoring, và deterministic beam-grid solver. Task #004 đã tạo CLI `simulate`/`recommend` và baseline simulation report.

---

## CLI

```powershell
cd MPC
python -m mpc simulate --artifact ..\ARX\arx_model.json --input ..\ARX\greenhouse_data.csv --output reports\v2_simulation.json --max-steps 288
python -m mpc recommend --artifact ..\ARX\arx_model.json --state-json state.json --output recommendation.json
```

V3 `adaptive-simulate` và `closed-loop` thuộc task sau.

---

## Tests

```powershell
python -m pytest MPC/tests -q
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MPC_ACTUATOR_URL` | v3 only | HTTP endpoint nhận command bơm |
| `MPC_ACTUATOR_TOKEN` | v3 only | Bearer token gửi actuator command |
| `MPC_CONFIG_PATH` | No | Đường dẫn config override nếu không dùng default |

---

## Status

Current: task #004 added `python -m mpc simulate` and `python -m mpc recommend`, including threshold baseline comparison and JSON report metrics.

Core runtime bắt đầu từ task #002; solver/recommendation đã có ở task #003; CLI/simulation đã có ở task #004; v3 adaptive/closed-loop tiếp tục ở task #006/#007.
