# Changelog

## [Unreleased]

### Added

- V2 CLI `python -m mpc simulate` để so sánh MPC với threshold baseline và ghi JSON report.
- V2 CLI `python -m mpc recommend` để đọc state JSON và ghi recommendation JSON.
- V2 validation gate reference and expanded pytest coverage for config, CLI errors, and simulation regression.
- V3 AMPC bias adaptation layer with guarded residual updates and bias-corrected horizon forecasts.
- V3 CLI `python -m mpc adaptive-simulate` để so sánh `mpc`, `ampc`, và threshold baseline.
- Simulation reports include observation-error metrics for controller-vs-fixture comparison.
- V3 HTTP actuator pilot with `ActuatorCommand`, Bearer auth from env, `closed-loop` CLI, and fake HTTP actuator tests.
- Runnable MPC/AMPC demo examples and validation documentation for v2 recommendation, v2 simulation, v3 adaptive simulation, and v3 closed-loop dry check.
- CLI defaults for artifact/state/input/output paths, `auto` alias for closed-loop runtime, and `config-schema` export for website-facing defaults/field groups.

### Fixed

- Objective cost normalize water/switching bằng `pump.max_seconds` và daily cap bằng `soft_daily_pump_cap_seconds`, đúng theo biên điều khiển bơm.
- `recommend` CLI output ghi đúng public contract top-level thay vì wrap trong envelope.
- Simulation report objective cost reset soft daily pump cap theo ngày lịch thay vì cộng dồn toàn bộ CSV như một ngày.
- Direct API `run_adaptive_simulation()` luôn bật bias adaptation nội bộ để không trả report `ampc` tĩnh khi caller dùng `ControllerConfig()` mặc định.
- `run_closed_loop()` validate actuator config trước khi dùng injected actuator client, nên fake/test client không bypass được guard explicit config.
