# Mini Greenhouse ARX(2,2,1) Rework Plan

## Mục tiêu

Đưa toàn bộ đồ án về một baseline rõ ràng, nhất quán và đủ thực tế cho bối cảnh **nhà kính mini**:

- Mô hình mục tiêu vẫn là **ARX(2,2,1)**
- Dữ liệu synthetic phải phản ánh được logic vận hành nhà kính mini
- Notebook phải fit đúng cấu trúc đó, không “né” dữ liệu bằng cách đổi model order sai mục tiêu
- Kết quả đánh giá phải đáng tin, tránh kiểu train đẹp giả nhưng không có ý nghĩa thực tế

## Vấn đề hiện tại

### 1. Generator và file CSV chưa chắc đang cùng một version

`data_generator.py` hiện đã được kéo về đúng tinh thần `ARX(2,2,1)`, nhưng `greenhouse_data.csv` có thể vẫn là bộ dữ liệu cũ nếu notebook chưa regenerate lại.

Hệ quả:

- notebook có thể đang fit đúng code mới nhưng dữ liệu lại từ generator cũ
- `true_params` trong `arx_model.json` có thể không khớp file `data_generator.py` hiện tại
- rất dễ đánh giá sai generator hoặc sai notebook chỉ vì lệch version dữ liệu

### 2. Vấn đề lớn nhất của notebook là phương pháp fit, không chỉ là model order

Lỗi nghiêm trọng từng gặp là:

- fit ARX trên **min-max normalized space**
- lại để `INCLUDE_INTERCEPT = False`

Với ARX, cách làm đó dễ tạo ra mô hình:

- one-step prediction rất đẹp
- nhưng free-run simulation trôi mạnh
- parameter khó giữ ý nghĩa vật lý

Đây là nguyên nhân lớn khiến kết quả nhìn “ảo” dù train/validation one-step có thể cao.

### 3. Dữ liệu chưa chắc đủ giàu để nhận dạng tốt

Ngay cả khi generator đúng cấu trúc, bộ data vẫn có thể chưa tốt nếu:

- một actuator gần như luôn OFF hoặc luôn ON
- đất ở quá lâu ngoài dải setpoint
- tín hiệu điều khiển thiếu số lần chuyển trạng thái
- môi trường chỉ dao động nhẹ và ít kích thích động học

### 4. Động học vẫn cần bám hơn với nhà kính mini

Các điểm phải tiếp tục để ý:

- `Drip` cần có tính pulse và độ trễ thấm hợp lý
- `Mist` chủ yếu nên tác động qua `Humidity`, không làm đất tăng ẩm quá mạnh
- `Fan` phải làm khô vừa phải, không phi thực tế
- môi trường trong nhà kính phải có quán tính, không đổi tức thời

### 5. Cách đánh giá phải ưu tiên free-run

Các lỗi cần tránh:

- chỉ nhìn train metrics
- chỉ nhìn one-step validation
- đánh giá trên normalized space
- không kiểm tra duty cycle actuator và vùng hoạt động so với setpoint

## Spec mới cần bám theo

### 1. Cấu trúc mô hình mục tiêu

Mục tiêu thống nhất cho toàn bộ dự án:

```text
ARX(na, nb, nk) = ARX(2, 2, 1)
```

Tức là:

```text
Soil(t) =
    a1 * Soil(t-1) + a2 * Soil(t-2)
  + b_temp_1 * Temp(t-1) + b_temp_2 * Temp(t-2)
  + b_humi_1 * Humi(t-1) + b_humi_2 * Humi(t-2)
  + b_light_1 * Light(t-1) + b_light_2 * Light(t-2)
  + b_drip_1 * Drip(t-1) + b_drip_2 * Drip(t-2)
  + b_mist_1 * Mist(t-1) + b_mist_2 * Mist(t-2)
  + b_fan_1 * Fan(t-1) + b_fan_2 * Fan(t-2)
  + e(t)
```

### 2. Logic nhà kính mini cần phản ánh

Generator phải có:

- chu kỳ ngày/đêm
- thời tiết ngày khác nhau
- setpoint `Soil_Low_SP` và `Soil_High_SP`
- hysteresis cho tưới
- minimum on/off time để tránh bật tắt liên tục
- `Drip` có ảnh hưởng mạnh nhưng có độ trễ thấm đất
- `Mist` tác động chủ yếu qua tăng `Humidity`, ảnh hưởng đất nhỏ hơn `Drip`
- `Fan` làm giảm `Temperature`, giảm `Humidity`, và làm đất khô nhanh hơn
- nhiễu quá trình vừa phải, không làm tín hiệu quá lý tưởng

### 3. Yêu cầu để kết quả “đáng tin”

Notebook cần:

- fit đúng `ARX(2,2,1)` theo spec
- fit trực tiếp trên **original engineering units**
- mặc định **không lọc** tín hiệu trước khi fit
- ưu tiên đánh giá trên **free-run validation**
- in metrics trực tiếp trên **original space**
- so sánh parameter ước lượng với true parameters của generator khi dùng synthetic data
- in thêm tóm tắt excitation:
  - tỷ lệ ON của `Drip`, `Mist`, `Fan`
  - số lần switching
  - tỷ lệ `Soil_Moisture` nằm dưới/trong/trên dải setpoint

## Những thay đổi cần làm

### A. Với `data_generator.py`

- giữ `TRUE_PARAMS` đầy đủ cho `ARX(2,2,1)`
- đảm bảo file CSV được regenerate lại sau mỗi lần đổi generator
- tiếp tục tune để:
  - `Drip` không làm đất vượt setpoint quá lâu
  - `Mist` và `Fan` xuất hiện đủ để nhận dạng
  - duty cycle và switching hợp lý cho bối cảnh nhà kính mini
- giữ dải `Soil_Moisture` trong khoảng vận hành hợp lý, tránh saturate quá nhiều
- ưu tiên perturbation an toàn thay vì random override phá cấu trúc

### B. Với `ARX_Model_Notebook.ipynb`

- đặt lại baseline về `NA=2, NB=2, NK=1`
- giữ `INCLUDE_INTERCEPT = False` mặc định để đồng bộ với generator gốc trong original space
- giữ `APPLY_FILTERING = False` mặc định
- bỏ fit trên normalized space; fit trực tiếp trên original units
- sửa mọi cell simulation/prediction để dùng đúng số feature như regression matrix
- model selection phải ưu tiên **free-run**
- phần giải thích parameter phải map đúng cả lag 1 và lag 2
- export thêm metadata vận hành (`train_behavior`, `val_behavior`) để đọc chất lượng data nhanh

### C. Với docs

- tài liệu chính phải ghi rõ:
  - generator hiện nay đã sinh đúng `ARX(2,2,1)`
  - `Drip` có tác động mạnh hơn ở lag 2
  - notebook phải chạy theo flow `CSV -> generate fallback`
  - tiêu chí đánh giá nào mới đáng tin cho đồ án

## Tiêu chí chấp nhận

Đợt sửa này được xem là đạt khi:

- generator sinh dữ liệu đúng cấu trúc ARX(2,2,1)
- notebook regenerate đúng dataset mới nhất từ generator khi cần
- notebook chạy hết không lỗi
- notebook không cần hạ model xuống `NB=1`
- parameter ước lượng trên synthetic data có chiều tác động đúng
- không còn lệch lớn do fit trên normalized space không intercept
- free-run validation được xem là metric chính, không phải metric phụ
- bộ data có excitation chấp nhận được:
  - `Drip`, `Mist`, `Fan` đều có hoạt động
  - đất không nằm quá nhiều thời gian ngoài dải setpoint
- phần thuyết minh đủ thuyết phục cho đồ án nhà kính mini

## Thứ tự triển khai

1. Khóa notebook về original-space ARX(2,2,1) và clear output cũ
2. Regenerate lại `greenhouse_data.csv` từ generator hiện tại
3. Đọc lại duty cycle, setpoint occupancy, one-step và free-run
4. Tune tiếp `data_generator.py` nếu excitation hoặc operating band chưa ổn
5. Đồng bộ lại tài liệu chính và chốt cách trình bày cho đồ án
