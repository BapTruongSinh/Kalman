# MPC Onboarding Answers

> Created: 2026-05-08
> Scope: Q&A đã chốt để tạo project `MPC/` và tránh hỏi lại các quyết định đã có.

## Project Basics

| Question | Answer |
|----------|--------|
| Project name? | `MPC` |
| One-sentence description? | Controller cho smart greenhouse: v2 MPC khuyến nghị lệnh bơm nước, v3 AMPC thêm bias adaptation và closed-loop pilot. |
| Primary users? | Project owner/research implementer và greenhouse operator/demo user. |
| Problem solved? | Chuyển state độ ẩm đất từ Kalman thành lệnh bơm tối ưu hơn threshold/manual control. |

## Controller Scope Decisions

| Decision | Answer |
|----------|--------|
| V2 deliverable | Simulation + recommendation, chưa control phần cứng. |
| Folder location | `demo_kalman/MPC` ở repo root, peer với `Kalman/` và `ARX/`. |
| Control actuator | Chỉ một bơm nước. Không dùng Hybrid MPC hoặc Hierarchical MPC. |
| Command shape | `pump_seconds` mỗi step. |
| Step duration | 300 giây, khớp artifact/data hiện có. |
| Prediction horizon | 12 steps / 60 phút. |
| Pump limit | 0-300 giây mỗi step, map sang duty `Drip = pump_seconds / 300`. |
| Switching rule | Penalty-only, không hard min-run trong v2. |

## Model & Optimization Decisions

| Decision | Answer |
|----------|--------|
| V2 plant model | Reuse ARX artifact `../ARX/arx_model.json`, dùng input `Drip`. |
| Disturbances | `Temperature/Humidity/Light` dùng measured-hold forecast. |
| Target policy | Band tracking. |
| Default target band | 55-65%. |
| Band source | MPC config default; CSV setpoint có thể dùng cho simulation sau nếu cần. |
| Solver | Grid shooting deterministic, không thêm SciPy/CVXPY ở v2. |
| State input | Ưu tiên `kf_x_posterior`, fallback raw soil moisture. |
| Main metrics | Band violation + total water/pump seconds, thêm switching count và objective cost. |
| Public interface | Python package + CLI. |
| Water safety cap | Soft daily cap. |

## AMPC / Closed-Loop Decisions

| Decision | Answer |
|----------|--------|
| V3 adaptation method | Bias correction dựa trên prediction error/Kalman residual. |
| V3 integration scope | Closed-loop pilot. |
| Actuator channel | HTTP/MQTT device, chốt ưu tiên HTTP POST. |
| Auth | Bearer token. |
| Default closed-loop mode | Auto execute khi config explicit hợp lệ. |
| Fail-safe | Pump off + alert/log. |
| Stale sensor limit | 2 steps / 10 phút. |

## Open Items

| Item | Default / Status |
|------|------------------|
| Grid resolution | Chốt ở ADR-004: default 30 giây. |
| Cost weights | Chốt ở ADR-004: band `10.0`, terminal band `20.0`, water `0.2`, switching `0.5`, daily cap excess `2.0`. |
| Soft daily cap | Chốt ở ADR-004: `1800s/day` soft cap; vẫn cần calibration flow rate nếu đổi sang ml/L. |
| Actuator real endpoint | Chưa có; task #007 dùng env/config và fake actuator tests. |
| Pump flow rate | Deferred; hiện dùng seconds, chưa đổi sang ml/L. |
