# MPC Database Notes

V2 không sở hữu database schema và không ghi DB. `MPC/` đọc state từ JSON/CSV/simulation input để giữ controller độc lập với Django.

## Future Integration

Nếu sau này tích hợp với `Kalman/`, nguồn dữ liệu chính sẽ là:

- `PipelineCycle.kf_x_posterior` làm state chính.
- `PipelineCycle.raw_soil_moisture` làm fallback.
- `PipelineCycle.temperature`, `humidity`, `light` làm measured disturbance.
- `ExperimentRun` làm run identity.

Không thêm bảng mới cho MPC trong scaffold này. Nếu cần lưu recommendation/history, tạo task database riêng và cập nhật ADR trước.

