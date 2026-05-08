# Changelog

## [Unreleased]

### Added

- V2 CLI `python -m mpc simulate` để so sánh MPC với threshold baseline và ghi JSON report.
- V2 CLI `python -m mpc recommend` để đọc state JSON và ghi recommendation JSON.
- V2 validation gate reference and expanded pytest coverage for config, CLI errors, and simulation regression.

### Fixed

- `recommend` CLI output ghi đúng public contract top-level thay vì wrap trong envelope.
- Simulation report objective cost reset soft daily pump cap theo ngày lịch thay vì cộng dồn toàn bộ CSV như một ngày.
