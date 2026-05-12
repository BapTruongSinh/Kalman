# Hướng Dẫn Sử Dụng Green-House

## Cấu Hình AMPC Tự Động

Cấu hình AMPC tự động cho phép chỉnh thông số cây trồng, đất, bơm, và an toàn dùng cho tưới tự động.

### Cách cập nhật cấu hình FAO-56

1. Mở dashboard.
2. Vào Auto Settings.
3. Chọn soil preset phù hợp với luống trồng.
4. Kiểm tra `theta_fc`, `theta_wp`, và `theta_sat`.
5. Nhập crop, root depth, pump flow, irrigation area, location, và cost values.
6. Bấm Save.

**Kết quả mong đợi**: dashboard lưu profile cho greenhouse hiện tại. Các lần AMPC sau sẽ đổi độ ẩm đất dạng sensor-percent sang FAO-56 `theta`, `Dr`, `TAW`, và `RAW` trước khi chọn lệnh bơm.

### Lỗi thường gặp

**Save báo lỗi ở một field**

Giá trị đang nằm ngoài khoảng vật lý hợp lệ. Kiểm tra `theta_wp < theta_fc < theta_sat`, root depth dương, pump flow dương, và latitude/longitude hợp lệ.

**Soil preset làm đổi theta values**

Đây là hành vi đúng. Preset điền theta mặc định cho loại đất đó. Bạn vẫn có thể sửa theta trước khi lưu.

## Forecast Và FAO Audit

Trang Forecast hiển thị lệnh bơm AMPC và đồ thị dự báo sensor-percent.

### Cách đọc FAO audit panel

1. Mở Forecast.
2. Kiểm tra panel FAO-56 audit.
3. Đọc `Dr`, `TAW`, `RAW`, `Ks`, `ET0_step`, `ETc_adj`, và `irrigation_depth_mm`.
4. Dùng status pill để hiểu trạng thái nước hiện tại.

**Kết quả mong đợi**: `Wet / no-irrigation` nghĩa là `Dr = 0`. `Safe zone` nghĩa là `Dr <= RAW`. `Water stress` nghĩa là `Dr > RAW`.

Đường chart vẫn là sensor percent. Đó không phải volumetric water content và không phải `Dr`.

### Lỗi thường gặp

**FAO audit panel hiển thị placeholder**

Recommendation mới nhất được tạo trước khi có FAO audit fields, hoặc AMPC chưa tạo recommendation. Chạy AMPC lại sau khi lưu profile hợp lệ.

**AMPC báo lỗi nhưng không hiện chi tiết kỹ thuật**

UI ẩn backend stack trace và file path. Kiểm tra audit row ở backend nếu cần chẩn đoán nội bộ.
