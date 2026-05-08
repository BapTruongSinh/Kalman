---
id: "007"
title: "Add v3 closed-loop HTTP actuator pilot with fail-safe"
status: "todo"
area: "backend"
agent: "@builder"
required_skills: ["backend", "quality", "backend-security-coder"]
priority: "normal"
created_at: "2026-05-08"
due_date: null
started_at: null
completed_at: null
prd_refs: ["FR-030", "FR-031", "FR-032", "FR-033"]
blocks: ["008"]
blocked_by: ["003", "005", "006"]
---

## Description

Tạo actuator adapter cho v3 closed-loop pilot qua HTTP POST + Bearer token. Auto execute chỉ chạy khi config explicit hợp lệ; mọi lỗi safety phải pump off + alert/log.

## Acceptance Criteria

- [ ] Command payload đúng contract PRD.
- [ ] URL/token lấy từ env/config, không hardcode.
- [ ] Stale sample quá 10 phút, missing state, solver/model error, actuator HTTP failure đều fail closed.
- [ ] Tests dùng fake HTTP actuator; không gọi phần cứng thật.

## Completion Gates

- [ ] Logic: Command path chỉ auto execute khi config explicit hợp lệ; mọi lỗi đi qua pump off + alert/log.
- [ ] Nghiệp vụ: HTTP payload, stale limit 10 phút, và Bearer auth đúng PRD/Q&A.
- [ ] Security: URL/token lấy từ env/config, không log secret, validate outbound payload và timeout.
- [ ] Test chạy thực tế: Fake actuator tests, fail-safe tests, và relevant MPC tests đã pass.

## Technical Notes

Mặc dù user chọn auto execute, implementation phải có guard config explicit để tránh accidental actuation.

## History

| Date | Agent / Human | Event |
|------|--------------|-------|
| 2026-05-08 | Codex | Task created |
