# Phân Tích Chi Tiết Pipeline Và Hệ Báo Cáo ARX Model

## 1. Mục tiêu của tài liệu này

File này không nhắc lại toàn bộ đồ án theo kiểu tổng quan, mà tập trung đi sâu vào:

- kiến trúc `pipeline` trong [`arx_pipeline.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/arx_pipeline.py)
- lớp `reporting` trong [`arx_reporting.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/arx_reporting.py)
- cơ chế sinh notebook từ [`tools/rebuild_arx_notebook.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/tools/rebuild_arx_notebook.py)
- cơ chế thực thi notebook trong [`tools/execute_notebook.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/tools/execute_notebook.py)
- luồng dữ liệu từ `data -> model -> metrics -> artifact -> report`

Nếu bản [`BAO_CAO_ARXMODEL_VI.md`](C:/Users/minht/OneDrive/Desktop/ARX-Model/BAO_CAO_ARXMODEL_VI.md) là tài liệu để thuyết trình tổng thể, thì file này là tài liệu để:

- giải thích code với giảng viên
- bảo vệ logic thiết kế
- hiểu vì sao notebook hiển thị được các bảng và biểu đồ
- hiểu rõ vai trò của từng hàm trong pipeline

## 2. Sơ đồ kiến trúc toàn hệ thống

Nhìn ở mức cao, toàn bộ repo đang chia thành 5 lớp:

### Lớp 1. Sinh dữ liệu

File chính:

- [`data_generator.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py)

Vai trò:

- tạo dữ liệu synthetic cho nhà kính mini
- cung cấp `TRUE_PARAMS`
- tạo `greenhouse_data.csv`

### Lớp 2. Pipeline nhận dạng hệ

File chính:

- [`arx_pipeline.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/arx_pipeline.py)

Vai trò:

- nạp data
- split time series
- tạo regression matrix
- fit OLS
- mô phỏng 1-step, n-step, free-run
- đánh giá metrics
- residual diagnostics
- model search
- xuất `arx_model.json`

### Lớp 3. Reporting dataframe

File chính:

- [`arx_reporting.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/arx_reporting.py)

Vai trò:

- biến `results` từ pipeline thành các bảng trung gian
- chuẩn bị dữ liệu cho chart trong notebook
- chuẩn hóa phần trình bày, tránh nhồi logic vào notebook

### Lớp 4. Notebook generator

File chính:

- [`tools/rebuild_arx_notebook.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/tools/rebuild_arx_notebook.py)

Vai trò:

- tạo notebook như một báo cáo có cấu trúc
- notebook không phải viết tay hoàn toàn, mà được sinh từ script
- điều này giúp đồng bộ narrative và code

### Lớp 5. Notebook execution

File chính:

- [`tools/execute_notebook.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/tools/execute_notebook.py)

Vai trò:

- chạy notebook bằng `nbclient`
- ghi output lại vào chính file notebook

## 3. Luồng dữ liệu end-to-end

Luồng đầy đủ của dự án có thể đọc như sau:

1. `data_generator.py` tạo ra `greenhouse_data.csv` và `TRUE_PARAMS`
2. `arx_pipeline.py` đọc CSV hoặc regenerate data
3. Pipeline fit mô hình ARX và tạo object `results`
4. `artifact_payload()` biến `results` thành JSON-ready dict
5. `save_artifact()` lưu thành [`arx_model.json`](C:/Users/minht/OneDrive/Desktop/ARX-Model/arx_model.json)
6. Notebook dùng `run_pipeline()` để lấy lại `results`
7. `arx_reporting.py` tách `results` thành nhiều bảng con phục vụ chart
8. Notebook hiển thị bảng, biểu đồ, research notes

Điểm hay ở đây là:

- phần tính toán và phần trình bày đã được tách tương đối sạch
- notebook không phải là nơi chứa logic fit chính
- notebook là nơi kể câu chuyện từ kết quả đã được pipeline chuẩn bị

## 4. Phân tích chi tiết `arx_pipeline.py`

### 4.1 Nhóm hằng số đầu file

Pipeline định nghĩa:

- `DEFAULT_INPUT_COLS = ["Temperature", "Humidity", "Light", "Drip", "Mist", "Fan"]`
- `DEFAULT_OUTPUT_COL = "Soil_Moisture"`
- `DEFAULT_REQUIRED_COLUMNS`

Ý nghĩa:

- khóa cứng baseline theo đúng bài toán đang làm
- tránh việc notebook tự ý truyền thiếu cột

### 4.2 `DataConfig`

`DataConfig` tách cấu hình dữ liệu khỏi logic xử lý. Nó chứa:

- đường dẫn CSV
- đường dẫn script generator
- cờ regenerate dữ liệu
- số ngày sinh dữ liệu
- chu kỳ lấy mẫu
- seed và start date

Ý nghĩa kiến trúc:

- pipeline có thể chạy ở cả chế độ “replay từ CSV” và “rebuild từ generator”
- code linh hoạt nhưng vẫn có cấu hình rõ ràng

### 4.3 `SplitConfig`

`SplitConfig` quản lý tỷ lệ train/validation/test và có `validate()` để kiểm tra:

- tỷ lệ có hợp lệ không
- tổng có bằng 1 không
- test ratio có dương không

Đây là bước nhỏ nhưng rất quan trọng để tránh lỗi logic ngay từ đầu.

### 4.4 `ModelConfig`

`ModelConfig` là nơi khóa cấu trúc mô hình:

- `na`
- `nb`
- `nk`
- `include_intercept`
- `input_cols`
- `output_col`

Property `param_names` cực kỳ quan trọng vì nó nối được:

- thứ tự cột của regression matrix
- thứ tự phần tử trong `theta`
- tên hiển thị trong bảng và biểu đồ

### 4.5 `load_or_generate_data()`

Đây là cổng vào của dữ liệu. Logic là:

- nếu CSV tồn tại và không ép regenerate thì đọc CSV
- ngược lại thì gọi generator để sinh lại data
- nếu có generator thì vẫn cố lấy `true_params` để dùng cho đối chiếu synthetic

Điểm mạnh:

- reproducible
- linh hoạt

Điểm rủi ro:

- CSV và generator có thể lệch version nếu không kiểm soát chặt

### 4.6 `split_time_series()`

Hàm này chia dữ liệu tuần tự thành:

- `df_train`
- `df_val`
- `df_test`

Điểm quan trọng là:

- không shuffle
- không random split

Điều này hoàn toàn đúng với time series và bài toán mô phỏng điều khiển.

### 4.7 `summarize_dataset_behavior()`

Hàm này tóm tắt hành vi vận hành của từng split:

- số dòng
- khoảng thời gian
- tháng và mùa xuất hiện
- duty cycle của actuator
- số lần switching
- mức bám setpoint

Đây là cầu nối giữa data engineering và system identification. Nếu không có phần này, báo cáo metric sẽ rất thiếu thuyết phục.

### 4.8 `build_regression_matrix()`

Đây là một trong những hàm cốt lõi nhất. Nó biến dataframe thành bài toán hồi quy tuyến tính chuẩn bằng cách ghép:

- output trễ
- input trễ theo `nk` và `nb`
- intercept nếu bật

Kết quả là:

- `x_mat`
- `y_vec`

Hàm này được tái sử dụng cho cả baseline lẫn model search.

### 4.9 `estimate_ols()`

Hàm này giải bài toán least squares và trả về:

- `theta`
- `cov`
- `sigma2`

Điểm hay là pipeline không chỉ fit ra hệ số, mà còn chuẩn bị covariance để về sau tính được confidence interval.

### 4.10 `compute_metrics()`

Hàm này thống nhất việc tính:

- `RMSE`
- `MAE`
- `Bias`
- `FIT`
- `R2`
- `AIC`
- `BIC`

Cùng một hàm được dùng cho 1-step, n-step và free-run, nên việc so sánh giữa các mode là nhất quán.

### 4.11 `simulate_arx()`

Đây là hàm free-run simulation. Mỗi bước dự đoán dùng chính giá trị dự đoán trước đó thay vì ground truth.

Ý nghĩa:

- bộc lộ lỗi tích lũy
- phản ánh bài toán mô phỏng thực sự

### 4.12 `simulate_arx_n_step()`

Hàm này mô phỏng trung gian giữa 1-step và free-run:

- lấy history thật đến một origin
- từ đó dự báo tiến lên `n_steps`
- lấy giá trị ở thời điểm đích

Trong notebook hiện tại, `n_step = 12`.

### 4.13 `summarize_parameters()`

Hàm này biến `theta` thành bảng tham số dễ đọc với:

- estimate
- std
- CI 95%
- true value
- delta so với true
- sign_ok

Đây là nguồn dữ liệu cho phần parameter recovery trong notebook.

### 4.14 `compute_ar_roots()`

Hàm này dùng để kiểm tra ổn định động học của phần AR bằng cách tính các nghiệm và độ lớn của chúng.

### 4.15 `residual_diagnostics()`

Đây là một trong những hàm khoa học quan trọng nhất của pipeline. Nó tính:

- residual mean
- residual std
- normality tests
- Ljung-Box
- residual-input correlation

Ý nghĩa:

- chứng minh residual đã gần nhiễu hơn
- cho thấy mô hình đã bắt được phần tuyến tính đáng lẽ phải bắt

### 4.16 `evaluate_slice()`

Đây là “hộp đánh giá chuẩn” của pipeline. Nó làm trọn gói cho từng split:

1. build regression matrix
2. tính 1-step
3. tính free-run
4. tính n-step
5. tính metric
6. residual diagnostics
7. behavior summary
8. theoretical free-run ceiling nếu có `true_theta`

### 4.17 `model_selection_search()`

Hàm này duyệt grid `(na, nb, nk)`, fit trên train, đánh giá trên validation, rồi xếp hạng candidate theo hiệu năng free-run.

Điểm tốt là:

- search không dùng test
- test vẫn giữ vai trò đánh giá cuối cùng

### 4.18 `artifact_payload()` và `run_pipeline()`

`run_pipeline()` là API nội bộ trung tâm của toàn project. Nó:

- nạp data
- split
- fit baseline
- đánh giá train/val/test
- chạy model search
- gắn best candidate
- trả về object `results`

`artifact_payload()` biến `results` thành bản JSON-ready để lưu lại thành [`arx_model.json`](C:/Users/minht/OneDrive/Desktop/ARX-Model/arx_model.json).

## 5. Cấu trúc dữ liệu `results`

`results` là object trung tâm được chia sẻ giữa:

- pipeline
- artifact
- reporting
- notebook

Nó chứa:

- config
- dataframe full/train/val/test
- parameter summary
- metrics theo split
- arrays prediction
- residual diagnostics
- model selection
- best candidate

Thiết kế này rất tiện vì notebook chỉ cần nắm một object duy nhất nhưng có thể truy cập toàn bộ thông tin cần thiết.

## 6. Phân tích chi tiết `arx_reporting.py`

Nếu `arx_pipeline.py` là nơi “tính”, thì `arx_reporting.py` là nơi “đóng gói để kể chuyện”.

Các hàm chính:

- `prediction_frame_for_split()`: ghép prediction với dataframe gốc
- `combined_prediction_frame()`: gộp train/val/test
- `parameter_frame()`: bảng tham số
- `standardized_parameter_frame()`: hệ số chuẩn hóa
- `behavior_frame()`: hành vi vận hành theo split
- `monthly_signal_summary()`: thống kê tín hiệu theo tháng
- `monthly_actuator_summary()`: duty cycle và switching theo tháng
- `monthly_setpoint_summary()`: mức bám setpoint theo tháng
- `rolling_rmse()`: RMSE cửa sổ trượt
- `contribution_frame()`: mức đóng góp của từng regressor
- `impulse_response_frame()`: đáp ứng xung
- `grouped_metrics()`: metric theo nhóm
- `model_comparison_frame()`: so sánh baseline và best candidate
- `selection_metric_grid()`: dựng heatmap model search

Ý nghĩa kiến trúc:

- pipeline không bị ô nhiễm bởi logic trình bày
- notebook không bị ô nhiễm bởi logic reshape dữ liệu

## 7. Notebook generator và notebook execution

### 7.1 `tools/rebuild_arx_notebook.py`

Script này sinh notebook như một báo cáo có cấu trúc, dùng:

- `md_cell()`
- `code_cell()`
- `desired_order`

Lợi ích:

- kiểm soát thứ tự cell
- giữ narrative nhất quán
- dễ refactor và sinh lại notebook sạch

### 7.2 `tools/execute_notebook.py`

Script này dùng `NotebookClient` để:

- đọc notebook
- chạy notebook
- ghi output lại vào chính file notebook

Điều này tạo ra quy trình 2 bước rõ ràng:

1. rebuild notebook
2. execute notebook

## 8. Pipeline và reporting nối với nhau như thế nào

Notebook không tự fit. Notebook chỉ gọi:

```python
results = run_pipeline(DATA_CONFIG, SPLIT_CONFIG, MODEL_CONFIG)
```

Sau đó:

- `arx_reporting.py` dựng các dataframe trung gian
- notebook dùng các dataframe đó để vẽ bảng, biểu đồ, và research notes

Ý nghĩa:

- một nguồn sự thật duy nhất cho kết quả
- dễ bảo trì
- dễ giải thích với giảng viên

## 9. Điểm mạnh của kiến trúc hiện tại

- Tách lớp tương đối tốt
- Notebook không ôm phần fit
- Có artifact JSON chuẩn hóa
- Có model search nhưng vẫn giữ baseline rõ ràng
- Có lớp reporting để kể chuyện bằng dữ liệu

## 10. Điểm yếu hoặc có thể cải thiện

- Chưa có test tự động
- Có rủi ro lệch version giữa generator và CSV
- `compute_ar_roots()` mới tối ưu cho `na=2`
- Dependency chạy notebook chưa khai báo đủ rõ cho môi trường sạch
- Condition number khá cao nên cần thận trọng khi diễn giải hệ số

## 11. Cách dùng tài liệu này khi bảo vệ

Nếu giảng viên hỏi về kiến trúc, bạn có thể trả lời theo 3 tầng:

### Tầng 1. Toàn hệ

- Em tách hệ thành generator, pipeline, reporting, notebook builder và notebook executor.

### Tầng 2. Lõi mô hình

- `run_pipeline()` là API nội bộ chính, trả về object `results` chứa toàn bộ dữ liệu cần cho đánh giá và báo cáo.

### Tầng 3. Báo cáo

- Notebook không tự fit mô hình mà chỉ gọi `run_pipeline()` và `arx_reporting.py` để hiển thị lại bằng bảng, biểu đồ và diễn giải.

## 12. Kết luận

Nhìn riêng dưới góc độ kiến trúc `pipeline + reporting`, dự án ARX Model của bạn đang có cấu trúc khá trưởng thành cho một đồ án:

- có lớp sinh dữ liệu rõ
- có pipeline fit và đánh giá tập trung
- có lớp reporting để kể chuyện bằng dữ liệu
- có notebook generator để chuẩn hóa narrative
- có artifact JSON để lưu snapshot kết quả

Điểm mạnh nhất của thiết kế hiện tại là:

- **logic mô hình nằm trong code Python**
- **logic trình bày nằm trong lớp reporting và notebook**
- **notebook đóng vai trò báo cáo, không phải nơi nhồi toàn bộ thuật toán**
