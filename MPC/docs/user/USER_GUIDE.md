# MPC User Guide

`MPC/` là package/CLI độc lập cho controller tưới nước. V2 hỗ trợ chạy recommendation một bước và simulation so sánh MPC với threshold baseline. V2 không ghi database và không điều khiển phần cứng.

## V2 Commands

Chạy từ thư mục `MPC/` để Python thấy package `mpc`:

```powershell
cd MPC
python -m mpc simulate --artifact ..\ARX\arx_model.json --input ..\ARX\greenhouse_data.csv --output reports\v2_simulation.json --max-steps 288
python -m mpc recommend --artifact ..\ARX\arx_model.json --state-json state.json --output recommendation.json
```

`simulate` đọc CSV có các cột `Timestamp`, `Soil_Moisture`, `Temperature`, `Humidity`, `Light`, và các cột actuator tùy chọn `Drip`, `Mist`, `Fan`. Report JSON gồm threshold baseline definition, band violation, total pump seconds, switching count, objective cost, và safety counts.

`recommend` đọc state JSON theo contract trong `docs/technical/API.md`. Nếu không truyền `--history-json`, CLI tạo history tối thiểu bằng cách lặp state hiện tại đủ số lag ARX cần.

## Recommend State JSON

```json
{
  "timestamp": "2026-05-08T10:00:00Z",
  "kf_x_posterior": 58.2,
  "raw_soil_moisture": 58.5,
  "temperature": 27.0,
  "humidity": 74.0,
  "light": 300.0,
  "last_pump_seconds": 0.0
}
```

## V3 Commands

```powershell
python -m mpc adaptive-simulate --artifact ..\ARX\arx_model.json --input ..\ARX\greenhouse_data.csv --output reports\v3_adaptive_simulation.json
python -m mpc closed-loop --config config\closed_loop.json
```

V3 commands vẫn thuộc task sau. Closed-loop pilot phải dùng fake actuator trước khi nối thiết bị thật.
