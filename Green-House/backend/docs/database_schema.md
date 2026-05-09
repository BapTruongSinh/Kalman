# Thiết kế cơ sở dữ liệu - Smart Greenhouse (1 khu, 4 cảm biến)

## Mục tiêu
Thiết kế này bám đúng phạm vi hiện tại:
- chỉ **1 nhà kính**
- chỉ **1 bộ cảm biến chính** gắn trên ESP32
- chỉ **4 chỉ số cố định**: nhiệt độ, độ ẩm không khí, ánh sáng, độ ẩm đất
- toàn bộ dữ liệu cảm biến phải lưu xuống MySQL

## Các bảng chính

### 1. `sensor_data`
Bảng quan trọng nhất. Mỗi dòng là **1 lần ESP32 gửi đủ bộ dữ liệu**.

Cột chính:
- `temperature`
- `humidity`
- `light`
- `soil_moisture`
- `recorded_at`
- `received_at`
- `payload`

Thiết kế này là phù hợp nhất cho scope hiện tại vì:
- query chart đơn giản
- debug đơn giản
- không phải tạo nhiều bảng vô ích
- đúng với mô hình ESP32 gửi gói dữ liệu định kỳ

### 2. `device`
Lưu các thiết bị điều khiển và bộ điều khiển chính:
- `ESP32 Main`
- `Quạt`
- `Bơm`
- `Đèn`

### 3. `device_state`
Lưu trạng thái hiện tại của từng thiết bị:
- đang bật hay tắt
- mong muốn bật/tắt
- lệnh cuối cùng

### 4. `threshold_rule`
Lưu ngưỡng điều khiển/cảnh báo.
Mỗi metric thường có 2 rule:
- ngưỡng thấp (`lte`)
- ngưỡng cao (`gte`)

Ví dụ:
- `soil_moisture <= 35` -> bật bơm
- `soil_moisture >= 70` -> tắt bơm

### 5. `alert`
Lưu lịch sử cảnh báo.

### 6. `device_command`
Hàng đợi lệnh từ web/backend sang ESP32.

## ERD rút gọn
- `device` 1-1 `device_state`
- `device` 1-n `device_command`
- `device` 1-n `alert`
- `threshold_rule` 1-n `alert`
- `sensor_data` 1-n `alert`

## Vì sao không tách mỗi cảm biến một bảng?
Vì dự án này chỉ có 4 chỉ số cố định và luôn gửi cùng lúc. Tách bảng sẽ làm:
- query rối hơn
- join nhiều hơn
- frontend chart khó hơn
- code ingest khó hơn

Nên dùng **1 bảng `sensor_data`** là đúng nhất cho phạm vi hiện tại.
