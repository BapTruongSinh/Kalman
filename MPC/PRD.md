# Product Requirements Document - MPC / AMPC Controller

> Source of truth cho `MPC/`. Tài liệu này được tạo từ onboarding MPC ngày 2026-05-08 và kế hoạch v2/v3 đã được user duyệt.

---

**Version**: 1.0
**Status**: Draft
**Last updated by human**: 2026-05-08
**Product owner**: Project owner

---

## 1. Executive Summary

`MPC/` xây dựng controller tưới nước cho smart greenhouse dựa trên state estimation đã có ở `Kalman/`. V2 là SISO MPC cho một bơm nước, chạy simulation và recommendation, chưa điều khiển phần cứng. V3 nâng lên AMPC bằng bias adaptation từ sai số dự báo/Kalman residual và có closed-loop pilot qua HTTP POST với fail-safe nghiêm ngặt. Project không dùng Hybrid MPC hoặc Hierarchical MPC vì hiện chỉ điều khiển một actuator là bơm nước.

---

## 2. Problem Statement

### 2.1 Current Situation

`Kalman/` đã có live-only pipeline: ingest sensor, ARX prior, Adaptive Kalman posterior, MySQL trace, dashboard online. Tuy nhiên repo chưa có controller thực sự để biến state độ ẩm đất thành lệnh bơm.

### 2.2 The Problem

Điều khiển tưới thủ công hoặc threshold-based phản ứng chậm, dễ tưới quá mức, và không tận dụng được dự báo động học. Cần một controller có thể nhìn trước trong horizon, cân bằng giữa giữ độ ẩm trong band và giảm nước/switching.

### 2.3 Why Now

Estimator live-only đã ổn định, ARX artifact đã có input `Drip`, và user đã chốt scope controller chỉ điều khiển bơm nước. Đây là thời điểm phù hợp để tách controller thành project riêng để phát triển v2 MPC rồi nâng lên v3 AMPC.

---

## 3. Goals & Success Metrics

### 3.1 Goals

- Tạo package/CLI MPC độc lập, có thể chạy simulation và recommendation không phụ thuộc Django runtime.
- Dùng ARX artifact hiện có làm plant model ban đầu và map `pump_seconds / 300` sang `Drip`.
- Đánh giá controller bằng band violation, tổng thời gian bơm, switching count, và objective cost.
- V3 thêm bias adaptation và closed-loop pilot an toàn qua HTTP actuator adapter.

### 3.2 Success Metrics

| Metric | Baseline | Target | How Measured |
|--------|----------|--------|--------------|
| Band violation time | Threshold baseline | MPC không tệ hơn baseline và ưu tiên giảm violation | Simulation report |
| Total pump seconds | Threshold baseline | MPC dùng nước không cao bất hợp lý khi cùng violation | Simulation report |
| Switching count | Threshold baseline | Lệnh không dao động quá mức nhờ switching penalty | Simulation report |
| Solver determinism | N/A | Cùng input cho cùng output | Unit tests |
| Safety fail-closed | N/A | 100% lỗi stale/model/API trả pump off | Safety tests |

---

## 4. User Personas

### Persona: Project Owner / Research Implementer

- **Role**: Người xây dựng và bảo vệ project smart greenhouse.
- **Goals**: Có controller MPC/AMPC rõ ràng, test được, giải thích được bằng mô hình và metric.
- **Pain points**: Code controller lẫn vào estimator sẽ khó review; controller thiếu fail-safe sẽ nguy hiểm khi lên phần cứng.
- **Technical level**: Developer/research.
- **Usage frequency**: Thường xuyên trong giai đoạn implementation và demo.

### Persona: Greenhouse Operator

- **Role**: Người vận hành nhà kính nhỏ/demo.
- **Goals**: Nhận đề xuất hoặc lệnh bơm giúp giữ độ ẩm đất trong vùng an toàn.
- **Pain points**: Threshold/manual control phản ứng chậm và có thể lãng phí nước.
- **Technical level**: Non-technical to moderate.
- **Usage frequency**: Khi chạy demo hoặc pilot.

---

## 5. Functional Requirements

### 5.1 Project Scaffold

- **FR-001**: Project phải có folder `MPC/` riêng ở repo root với README, PRD, TODO, `.tasks/`, docs technical/user/content/plan.
- **FR-002**: Project phải lưu Q&A onboarding MPC để các quyết định đã chốt không bị hỏi lại.
- **FR-003**: Backlog MPC phải có task thật cho v2/v3, không để placeholder template.

### 5.2 V2 MPC Simulation & Recommendation

- **FR-010**: MPC phải dùng step `300s`, horizon `12`, target band mặc định `55-65%`.
- **FR-011**: MPC phải nhận state ưu tiên `kf_x_posterior`, fallback `raw_soil_moisture`.
- **FR-012**: MPC phải biểu diễn control là `pump_seconds` trong `[0, 300]` mỗi step.
- **FR-013**: Plant model v2 phải reuse `../ARX/arx_model.json` và map `pump_seconds / 300` vào ARX input `Drip`.
- **FR-014**: Disturbance `Temperature/Humidity/Light` trong v2 dùng measured-hold forecast.
- **FR-015**: Solver v2 dùng deterministic grid shooting, không yêu cầu SciPy/CVXPY.
- **FR-016**: Recommendation output phải có `pump_seconds`, `step_seconds`, `predicted_soil_moisture`, `target_band`, `cost`, `safety_status`, `reason`.
- **FR-017**: Simulation report phải so sánh MPC với threshold baseline bằng band violation, total pump seconds, switching count, objective cost.

### 5.3 V3 AMPC

- **FR-020**: AMPC phải thêm bias correction dựa trên prediction error/Kalman residual gần đây.
- **FR-021**: Adaptive simulation phải so sánh v2 MPC và v3 AMPC trên cùng fixture/report.
- **FR-022**: Adaptation phải có guard để không làm mất fail-safe khi residual thiếu, stale, hoặc outlier.

### 5.4 Closed-Loop Pilot

- **FR-030**: V3 closed-loop pilot phải gửi actuator command bằng HTTP POST với Bearer token từ env/config.
- **FR-031**: Command payload phải gồm `command_id`, `timestamp`, `run_id`, `pump_seconds`, `step_seconds`, `mode`, `reason`, `safety_status`.
- **FR-032**: Nếu thiếu URL/token, sample stale quá 10 phút, state thiếu, solver lỗi, model lỗi, hoặc actuator API lỗi, controller phải fail closed: pump off + alert/log.
- **FR-033**: Auto execute chỉ được chạy khi config explicit hợp lệ; test phải dùng fake actuator, không gọi phần cứng thật.

---

## 6. Non-Functional Requirements

### Performance

- Solve v2 recommendation cho horizon 12 phải đủ nhanh cho chu kỳ 5 phút; target local p95 dưới 1 giây.

### Security

- Không commit secret.
- Bearer token chỉ lấy từ env/config runtime.
- Actuator command phải validate bounds trước khi gửi.

### Reliability

- Fail-safe mặc định là pump off.
- CLI phải trả lỗi rõ ràng khi artifact/input/config không hợp lệ.

### Maintainability

- V2 phải giữ package độc lập với Django.
- API/interface phải đủ rõ để sau này tích hợp backend mà không rewrite solver.

---

## 7. Out of Scope

- Không implement Hybrid MPC hoặc Hierarchical MPC.
- Không control `Mist` hoặc `Fan`.
- Không ghi DB trong v2.
- Không thêm Django endpoint ở phase scaffold.
- Không điều khiển phần cứng thật trước khi task closed-loop pilot có fake tests và fail-safe.
- Không train lại ARX trong MPC v2.

---

## 8. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | Grid resolution cho `pump_seconds` nên là bao nhiêu giây? | Project owner | Answered by ADR-004: default `30s` |
| 2 | Cost weights cụ thể cho band/water/switching/daily cap là bao nhiêu? | Project owner | Answered by ADR-004: band `10.0`, terminal band `20.0`, water `0.2`, switching `0.5`, daily cap excess `2.0` |
| 3 | Soft daily cap mặc định là bao nhiêu giây/ngày? | Project owner | Answered by ADR-004: `1800s/day` soft cap |
| 4 | Actuator HTTP endpoint và payload final của thiết bị thật là gì? | Project owner | Open trước v3 pilot |
| 5 | Có flow rate bơm thật để đổi seconds sang ml/L không? | Project owner | Deferred |

---

## 9. Revision History

| Date | Author | Change Description |
|------|--------|--------------------|
| 2026-05-08 | Project owner / Codex | Initial MPC/AMPC project draft from approved plan and onboarding Q&A |
