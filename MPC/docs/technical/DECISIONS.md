# Architecture Decision Records

> Append-only decision log cho `MPC/`.

---

## Decision Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| ADR-001 | Separate root-level MPC project with Python package and CLI | Accepted | 2026-05-08 |
| ADR-002 | Use SISO grid-shooting MPC before AMPC | Accepted | 2026-05-08 |
| ADR-003 | Use HTTP actuator pilot with fail-closed safety | Accepted | 2026-05-08 |
| ADR-004 | Freeze V2 package boundary and default controller config | Accepted | 2026-05-08 |

---

## ADR-001: Separate Root-Level MPC Project With Python Package and CLI

**Date**: 2026-05-08
**Status**: Accepted
**Deciders**: Project owner / Codex

### Context

`Kalman/` đã là live-only estimator app. Controller cần phát triển nhanh nhưng không nên làm phức tạp Django runtime hoặc phá invariant live-only.

### Options Considered

1. **`Server/backend/mpc`**: tích hợp nhanh với backend nhưng coupling cao.
2. **`Kalman/MPC`**: vẫn nằm trong target Kalman, nhưng kém rõ khi controller là project riêng.
3. **Repo-root `MPC/`**: tách sạch controller khỏi estimator, vẫn reuse `ARX/` và `Kalman/` context.

### Decision

Chọn repo-root `MPC/` với Python package + CLI.

### Consequences

- **Positive**: Dễ test simulation, ít rủi ro ảnh hưởng Kalman.
- **Negative**: Backend/API integration cần task riêng sau này.
- **Neutral**: Global `.claude` rules phải hiểu thêm `MPC/` là project target thứ hai.

---

## ADR-002: Use SISO Grid-Shooting MPC Before AMPC

**Date**: 2026-05-08
**Status**: Accepted
**Deciders**: Project owner / Codex

### Context

User chỉ điều khiển một bơm nước. Hybrid/hierarchical MPC là quá mức cho một actuator.

### Options Considered

1. **Hybrid MPC**: phù hợp discrete logic phức tạp nhưng dư scope.
2. **Hierarchical MPC**: phù hợp multi-layer/multi-zone nhưng dư scope.
3. **SISO MPC -> AMPC**: đúng độ phức tạp hiện tại, có đường nâng cấp rõ.

### Decision

V2 dùng SISO MPC với grid shooting. V3 thêm bias correction thành AMPC.

### Consequences

- **Positive**: Dễ giải thích, ít dependency, test deterministic.
- **Negative**: Chưa tối ưu continuous QP chuẩn; grid resolution cần tradeoff.
- **Neutral**: Có thể đổi solver sau nếu cần mà giữ interface recommendation.

---

## ADR-003: Use HTTP Actuator Pilot With Fail-Closed Safety

**Date**: 2026-05-08
**Status**: Accepted
**Deciders**: Project owner / Codex

### Context

V3 cần closed-loop pilot nhưng chưa có protocol thiết bị chi tiết. Điều khiển bơm có rủi ro overwater nếu lỗi sensor/model/API.

### Options Considered

1. **HTTP POST**: dễ fake test, payload JSON rõ.
2. **MQTT**: hợp IoT nhưng cần broker/topic/QoS dependency.
3. **Local GPIO**: sát phần cứng nhưng phụ thuộc host/pin/quyền.

### Decision

Ưu tiên HTTP POST + Bearer token. Fail-safe mặc định pump off + alert/log.

### Consequences

- **Positive**: Tích hợp và test đơn giản.
- **Negative**: Thiết bị thật phải expose HTTP endpoint hoặc gateway.
- **Neutral**: MQTT có thể thêm sau bằng adapter khác.

---

## ADR-004: Freeze V2 Package Boundary And Default Controller Config

**Date**: 2026-05-08
**Status**: Accepted
**Deciders**: Project owner / Codex

### Context

Task #001 phải biến MPC PRD thành contract đủ cụ thể trước khi viết plant adapter, solver, simulation, AMPC, và actuator. Các lựa chọn còn mở là package boundary, grid resolution, default cost weights, và soft daily water cap. V2 phải độc lập Django, reuse `../ARX/arx_model.json`, và không thêm SciPy/CVXPY.

### Options Considered

1. **Một script `mpc.py` trước**: nhanh cho demo, nhưng khó test, khó nâng lên AMPC, và dễ trộn config, plant model, solver, simulation, actuator.
2. **Python package modular với dataclass contracts**: tốn setup hơn, nhưng tạo seam rõ cho plant adapter, solver, simulation, safety, và v3 actuator.
3. **Dùng optimization library ngay**: biểu diễn toán học sạch hơn, nhưng trái constraint v2 không dùng SciPy/CVXPY và tăng rủi ro dependency khi plant interface chưa chứng minh xong.

### Decision

Dùng package Python `mpc/` theo module map trong `ARCHITECTURE.md`, CLI entrypoints, frozen dataclass contracts, grid-shooting solver, và default config trong `docs/technical/CONFIG.md`.

Defaults:

- `step_seconds = 300`
- `horizon_steps = 12`
- `target_band = [55.0, 65.0]`
- `pump_seconds` bounds `[0.0, 300.0]`
- `grid_seconds = 30.0`
- cost weights: band `10.0`, terminal band `20.0`, water `0.2`, switching `0.5`, daily cap excess `2.0`
- soft daily cap `1800.0` pump seconds/day
- stale limit `600` seconds

### Consequences

- **Positive**: Tasks #002-#007 có module seam và config name rõ để implement.
- **Positive**: Grid size nhỏ và deterministic: 11 pump candidates mỗi step.
- **Negative**: Defaults là điểm bắt đầu cho research/demo, chưa phải giá trị agronomy đã field-calibrate.
- **Negative**: Grid shooting có thể cần pruning hoặc solver tốt hơn nếu sau này tăng số actuator.
- **Neutral**: Daily cap vẫn là penalty mềm tới khi có flow rate và crop water budget.
