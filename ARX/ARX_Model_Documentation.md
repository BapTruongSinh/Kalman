# ARX Model – Greenhouse Soil Moisture Prediction
## Tài liệu kỹ thuật đầy đủ (Full Technical Documentation)

**Phiên bản:** 2.0  
**Ngày:** 2026-03-24  
**Đối tượng:** Kỹ sư điều khiển, Data Scientist, Nghiên cứu sinh

---

## Mục lục

1. [Giới thiệu tổng quan](#1-giới-thiệu-tổng-quan)
2. [Lý thuyết ARX Model](#2-lý-thuyết-arx-model)
3. [Phát biểu bài toán](#3-phát-biểu-bài-toán)
4. [Cấu trúc mô hình ARX(2,2,1)](#4-cấu-trúc-mô-hình-arx221)
5. [Phương trình mô hình](#5-phương-trình-mô-hình)
6. [Vector tham số](#6-vector-tham-số)
7. [Formulation hồi quy tuyến tính](#7-formulation-hồi-quy-tuyến-tính)
8. [Dạng ma trận](#8-dạng-ma-trận)
9. [Ước lượng tham số – Least Squares](#9-ước-lượng-tham-số--least-squares)
10. [Dự đoán đầu ra](#10-dự-đoán-đầu-ra)
11. [Đánh giá mô hình](#11-đánh-giá-mô-hình)
12. [Chiến lược phân chia dữ liệu](#12-chiến-lược-phân-chia-dữ-liệu)
13. [Quy trình chuẩn bị dữ liệu](#13-quy-trình-chuẩn-bị-dữ-liệu)
14. [Hướng dẫn triển khai Python](#14-hướng-dẫn-triển-khai-python)
15. [Lựa chọn bậc mô hình (Order Selection)](#15-lựa-chọn-bậc-mô-hình-order-selection)
16. [Phân tích phần dư (Residual Analysis)](#16-phân-tích-phần-dư-residual-analysis)
17. [Hạn chế và mở rộng](#17-hạn-chế-và-mở-rộng)
18. [Tài liệu tham khảo](#18-tài-liệu-tham-khảo)

---

## Cách đọc nhanh

| Nếu bạn muốn... | Nên đọc phần |
|---|---|
| Hiểu nhanh bài toán và mô hình | Mục 1, 3, 4, 5 |
| Nắm công thức và cách ước lượng | Mục 6, 7, 8, 9 |
| Biết cách đánh giá mô hình | Mục 10, 11, 16 |
| Chuẩn bị dữ liệu cho đúng | Mục 12, 13 |
| Chạy code Python ngay | Mục 14 |
| Chọn lại bậc mô hình | Mục 15 |
| Biết giới hạn của ARX | Mục 17 |

## Ký hiệu cốt lõi

| Ký hiệu | Ý nghĩa | Ghi chú |
|---|---|---|
| `y(t)` | Soil Moisture tại thời điểm `t` | Output chính |
| `u(t)` | Vector input ngoại sinh | Gồm `Temp`, `Humidity`, `Light`, `Drip`, `Mist`, `Fan` |
| `na` | Số lag của output | Bậc AR |
| `nb` | Số lag của mỗi input | Bậc động học input |
| `nk` | Số bước trễ input | Input delay |
| `T_s` | Sampling period | Đơn vị giây |
| `φ(t)` | Regression vector | Chứa các giá trị trễ |
| `θ` | Vector tham số mô hình | Cần được ước lượng |
| `X`, `Y` | Ma trận hồi quy và vector đầu ra | Dùng cho Least Squares |

> **Tóm tắt một dòng:** tài liệu này đi từ ý nghĩa vật lý của bài toán nhà kính, đến công thức ARX(2,2,1), rồi kết thúc bằng pipeline Python có thể chạy trực tiếp.

---

## Baseline triển khai hiện tại trong repo

Để tránh lệch giữa tài liệu và code chạy thật, baseline đang được khóa như sau:

- Dữ liệu mặc định: **365 ngày**, `T_s = 300 s`, bao phủ đủ **12 tháng / 4 mùa**
- Flow dữ liệu: **`CSV -> generate fallback`**, mặc định regenerate từ `data_generator.py`
- Split mặc định: **Train 60% / Validation 20% / Test 20%**, tuần tự theo thời gian
- Không lọc tín hiệu trước khi fit (`APPLY_FILTERING = False`)
- Fit trực tiếp trên **original engineering units**
- Bộ ước lượng baseline: **Ordinary Least Squares** (`numpy.linalg.lstsq`)
- Cấu trúc baseline để báo cáo / giải thích: **ARX(2,2,1)**, `INCLUDE_INTERCEPT = False`
- Khi chấm chất lượng mô hình, ưu tiên:
  - đúng dấu / gần đúng tham số thật
  - residual diagnostics
  - `12-step` và `free-run` trên validation / test
  - so sánh với **theoretical deterministic free-run ceiling** khi dùng synthetic data

---

## 1. Giới thiệu tổng quan

### 1.1 Bối cảnh

Nhà kính thông minh (Smart Greenhouse) là hệ thống canh tác được tự động hóa, nơi các tham số môi trường như nhiệt độ, độ ẩm, ánh sáng và tưới tiêu được điều khiển chính xác để tối ưu hóa sự phát triển của cây trồng. Trong đó, **độ ẩm đất (Soil Moisture)** là tham số quan trọng nhất vì:

- Ảnh hưởng trực tiếp đến quá trình hấp thụ dinh dưỡng
- Quyết định lịch tưới nước tự động
- Liên quan đến năng suất và chất lượng nông sản

### 1.2 Tại sao dùng ARX Model?

Mô hình ARX (AutoRegressive with eXogenous inputs) được chọn vì:

| Tiêu chí | ARX | Neural Network | Physics-based |
|---|---|---|---|
| Độ phức tạp | Thấp | Cao | Rất cao |
| Dữ liệu cần thiết | Ít | Nhiều | Không cần |
| Khả năng giải thích | Cao | Thấp | Cao |
| Tính thời gian thực | Có | Hạn chế | Không |
| Phù hợp điều khiển | Rất tốt | Tốt | Trung bình |

ARX là nền tảng của nhận dạng hệ thống (System Identification) – lĩnh vực cốt lõi trong điều khiển tự động.

### 1.3 Mục tiêu

- Xây dựng mô hình ARX(2,2,1) dự đoán Soil Moisture
- Ước lượng 14 tham số từ dữ liệu thực nghiệm
- Đánh giá mô hình trên tập kiểm tra độc lập
- Cung cấp nền tảng cho thiết kế bộ điều khiển

---

## 2. Lý thuyết ARX Model

### 2.1 Định nghĩa tổng quát

Mô hình ARX tổng quát cho hệ SISO (Single Input Single Output):

```
A(q) y(t) = B(q) u(t) + e(t)
```

Trong đó:
- `A(q)` = đa thức AR (AutoRegressive) – mô tả động học output
- `B(q)` = đa thức eXogenous – mô tả ảnh hưởng input
- `q` = toán tử dịch chuyển trước (forward shift operator): `q·y(t) = y(t+1)`
- `q⁻¹` = toán tử dịch chuyển sau (backward shift): `q⁻¹·y(t) = y(t-1)`
- `e(t)` = nhiễu trắng (white noise), E[e(t)] = 0

### 2.2 Dạng đa thức

```
A(q) = 1 + a₁q⁻¹ + a₂q⁻² + ... + a_na·q^(-na)
B(q) = b₁q^(-nk) + b₂q^(-nk-1) + ... + b_nb·q^(-nk-nb+1)
```

### 2.3 Ý nghĩa các bậc

| Ký hiệu | Tên | Ý nghĩa |
|---|---|---|
| **na** | AR order | Số giá trị quá khứ của output được sử dụng |
| **nb** | Input order | Số bậc động học của mỗi input |
| **nk** | Input delay | Số bước thời gian trễ của input |

### 2.4 Tại sao ARX là tuyến tính?

ARX có dạng **tuyến tính trong tham số** – đây là tính chất quan trọng cho phép ước lượng chính xác bằng phương pháp Least Squares.

```
y(t) = φ(t)ᵀ θ + e(t)
```

Đây là điều mà nhiều mô hình phi tuyến (NARX, neural network) không có được.

---

## 3. Phát biểu bài toán

### 3.1 Hệ thống MISO

Hệ thống nhà kính được mô hình hóa như một hệ **MISO** (Multiple Input – Single Output):

**Output duy nhất y(t):**
```
y(t) = Soil Moisture(t)   [đơn vị: %, hoặc m³/m³]
```

**6 inputs u(t):**

| Số | Ký hiệu | Tên | Đơn vị | Loại |
|---|---|---|---|---|
| 1 | Temp(t) | Nhiệt độ không khí | °C | Môi trường |
| 2 | Humidity(t) | Độ ẩm không khí | % RH | Môi trường |
| 3 | Light(t) | Cường độ ánh sáng | lux | Môi trường |
| 4 | Drip(t) | Tưới nhỏ giọt | ON/OFF hoặc L/h | Actuator |
| 5 | Mist(t) | Hệ thống phun sương | ON/OFF hoặc L/h | Actuator |
| 6 | Fan(t) | Quạt thông gió | ON/OFF hoặc RPM | Actuator |

### 3.2 Lý do chọn từng input

**Temperature:** Nhiệt độ cao làm tăng tốc độ bay hơi nước từ đất (evapotranspiration), trực tiếp giảm soil moisture.

**Humidity:** Độ ẩm không khí thấp tạo gradient bay hơi cao hơn, làm đất khô nhanh hơn.

**Light:** Bức xạ quang hợp (PAR) kích hoạt quá trình thoát hơi nước qua lá (transpiration), gián tiếp rút nước từ đất.

**Drip:** Van tưới nhỏ giọt – tác động trực tiếp và chính yếu đến soil moisture. Có độ trễ khoảng 15-30 phút để nước thấm vào đất và lan tỏa đến cảm biến.

**Mist:** Phun sương tạo độ ẩm không khí cao, giảm bay hơi từ đất nhưng cũng có thể ẩm trực tiếp bề mặt đất.

**Fan:** Quạt tăng lưu thông không khí, tăng tốc bay hơi, gián tiếp giảm soil moisture.

---

## 4. Cấu trúc mô hình ARX(2,2,1)

```
ARX(na, nb, nk) = ARX(2, 2, 1)
```

### 4.1 Giải thích các bậc

**na = 2** (AR order):
- Sử dụng 2 giá trị quá khứ của Soil Moisture: y(t-1) và y(t-2)
- Mô tả **quán tính** (inertia) của hệ thống – đất không thay đổi độ ẩm đột ngột
- Phụ thuộc vào đặc tính của loại đất (cát, sét, mùn)

**nb = 2** (Input order):
- Mỗi input có 2 giá trị quá khứ được sử dụng
- Mô tả **động học** của từng input – ví dụ tưới nước có tác động kéo dài theo thời gian
- Tổng: 6 inputs × 2 lags = 12 hệ số B

**nk = 1** (Input delay):
- Input ảnh hưởng sau **1 bước thời gian**
- Phản ánh **độ trễ vật lý**: nước tưới cần thời gian thấm vào đất trước khi cảm biến đọc được
- Với sampling period T_s, thì nk=1 tương đương độ trễ T_s giây/phút

### 4.2 Sampling Period

Cần xác định T_s (giây) phù hợp với hệ thống. Gợi ý:
- T_s = 60s (1 phút): phù hợp cho hệ thống nhà kính nhỏ
- T_s = 300s (5 phút): phù hợp cho hệ thống lớn hơn

> **Quan trọng:** nk = 1 tương đương độ trễ = 1 × T_s. Nếu T_s = 5 phút, thì input ảnh hưởng sau 5 phút.

### 4.3 Ghi chú thực tế về độ trễ

Trong vận hành nhà kính thực tế, **không phải mọi input đều có cùng độ trễ vật lý**:

- `Fan` và `Mist` thường ảnh hưởng lên `Temperature/Humidity` gần như tức thời hoặc sau vài phút
- `Drip` thường ảnh hưởng lên cảm biến `Soil Moisture` **chậm hơn**, do còn thời gian thấm, lan tỏa và vị trí đặt cảm biến
- `Light` và `Temperature` tác động lên quá trình mất nước thường mang tính tích lũy, không phải một xung duy nhất

Vì vậy:

- `ARX(2,2,1)` phù hợp như **baseline model** khi muốn mô hình đơn giản, dễ ước lượng
- Nếu `T_s = 300s` và cảm biến đất đặt xa đầu tưới, `nk = 1` có thể **quá ngắn** cho kênh `Drip`
- Trong bài toán triển khai thật, nên cân nhắc:
  - tăng `nk`
  - tăng `nb`
  - hoặc dùng **delay khác nhau cho từng input** nếu framework cho phép

> **Khuyến nghị thực tế:** với tín hiệu tưới nhỏ giọt, hãy ước lượng delay từ dữ liệu thật bằng cross-correlation hoặc test step-response trước khi cố định `nk`.

---

## 5. Phương trình mô hình

### 5.1 Phương trình đầy đủ

```
Soil(t) = a₁·Soil(t-1) + a₂·Soil(t-2)
        + b₁·Temp(t-1)     + b₂·Temp(t-2)
        + b₃·Humidity(t-1) + b₄·Humidity(t-2)
        + b₅·Light(t-1)    + b₆·Light(t-2)
        + b₇·Drip(t-1)     + b₈·Drip(t-2)
        + b₉·Mist(t-1)     + b₁₀·Mist(t-2)
        + b₁₁·Fan(t-1)     + b₁₂·Fan(t-2)
        + e(t)
```

### 5.2 Dạng compact

```
y(t) = a₁y(t-1) + a₂y(t-2) + Σᵢ₌₁⁶ [bᵢ₁·uᵢ(t-1) + bᵢ₂·uᵢ(t-2)] + e(t)
```

### 5.3 Dạng toán tử q

```
(1 + a₁q⁻¹ + a₂q⁻²) y(t) = Σᵢ₌₁⁶ (bᵢ₁q⁻¹ + bᵢ₂q⁻²) uᵢ(t) + e(t)
```

### 5.4 Ý nghĩa vật lý từng hệ số

| Hệ số | Giá trị kỳ vọng | Ý nghĩa vật lý |
|---|---|---|
| a₁ | ~0.8 đến 0.95 | Quán tính cao của đất, giá trị dương |
| a₂ | ~-0.1 đến 0.1 | Bậc 2 thường nhỏ |
| b₁, b₂ (Temp) | Âm | Nhiệt độ cao → đất khô → moisture giảm |
| b₃, b₄ (Humidity) | Dương/nhỏ | Độ ẩm cao → giảm bay hơi → nhỏ |
| b₅, b₆ (Light) | Âm/nhỏ | Ánh sáng tăng transpiration |
| b₇, b₈ (Drip) | **Dương, lớn** | Tưới nhỏ giọt tăng moisture trực tiếp |
| b₉, b₁₀ (Mist) | Dương/nhỏ | Ảnh hưởng gián tiếp |
| b₁₁, b₁₂ (Fan) | Âm/nhỏ | Quạt làm tăng bay hơi |

---

## 6. Vector tham số

Vector tham số θ bao gồm **14 phần tử**:

```
θ = [a₁, a₂, b₁, b₂, b₃, b₄, b₅, b₆, b₇, b₈, b₉, b₁₀, b₁₁, b₁₂]ᵀ ∈ ℝ¹⁴
```

**Phân tích:**
- **2 hệ số AR:** a₁, a₂ (phần AutoRegressive)
- **12 hệ số eXogenous:** 6 inputs × 2 lags = 12 hệ số B

**Điều kiện đủ dữ liệu:** N >> 14 mẫu dữ liệu. Thực tế nên có N ≥ 140 (10× số tham số).

---

## 7. Formulation hồi quy tuyến tính

### 7.1 Regression Vector φ(t)

Tại thời điểm t, vector hồi quy có 14 phần tử:

```
φ(t) = [y(t-1), y(t-2),
         Temp(t-1), Temp(t-2),
         Humidity(t-1), Humidity(t-2),
         Light(t-1), Light(t-2),
         Drip(t-1), Drip(t-2),
         Mist(t-1), Mist(t-2),
         Fan(t-1), Fan(t-2)]ᵀ ∈ ℝ¹⁴
```

### 7.2 Mô hình hồi quy

```
y(t) = φ(t)ᵀ θ + e(t)
```

Đây là **linear regression model** cổ điển với cấu trúc ARX.

### 7.3 Giải thích notation

- `φ(t)` là vector input của regression (còn gọi là **regressor**)
- `θ` là vector tham số cần ước lượng
- `e(t)` là residual (sai số mô hình)
- `φ(t)ᵀ θ` là tích vô hướng (scalar product) → cho ra y(t)

---

## 8. Dạng ma trận

### 8.1 Xây dựng ma trận

Với N mẫu dữ liệu (sau khi loại bỏ max(na, nb+nk-1) = max(2, 2) = 2 mẫu đầu):

**Regression Matrix X:**
```
X = [φ(3)ᵀ]   ← hàng 1: t = 3
    [φ(4)ᵀ]   ← hàng 2: t = 4
    [  ...  ]
    [φ(N)ᵀ]   ← hàng N-2: t = N
```

X có kích thước: **(N-2) × 14**

Mỗi hàng của X:
```
X[t-2, :] = [y(t-1), y(t-2), Temp(t-1), Temp(t-2), ..., Fan(t-1), Fan(t-2)]
```

**Output Vector Y:**
```
Y = [y(3), y(4), ..., y(N)]ᵀ ∈ ℝ^(N-2)
```

### 8.2 Hệ phương trình

```
Y = X θ + e
```

Đây là hệ **overdetermined** (N-2 >> 14 phương trình, 14 ẩn số) → giải bằng Least Squares.

---

## 9. Ước lượng tham số – Least Squares

### 9.1 Bài toán tối ưu

Tìm θ̂ tối thiểu hóa tổng sai số bình phương:

```
J(θ) = ||Y - Xθ||² = Σₜ [y(t) - φ(t)ᵀθ]²
```

### 9.2 Nghiệm Ordinary Least Squares (OLS)

```
θ̂ = (XᵀX)⁻¹ XᵀY
```

**Điều kiện tồn tại nghiệm:** ma trận `XᵀX` phải **khả nghịch** (non-singular), tức là:
- N-2 ≥ 14 (đủ dữ liệu)
- Không có multi-collinearity giữa các cột của X
- Dữ liệu phải có **kích thích đủ phong phú** (sufficiently rich excitation)

### 9.3 Tính chất thống kê của OLS

Nếu e(t) là white noise với phương sai σ²:

```
Cov(θ̂) = σ² (XᵀX)⁻¹
```

Nghĩa là:
- θ̂ là **unbiased estimator**: E[θ̂] = θ
- θ̂ là **BLUE** (Best Linear Unbiased Estimator) theo định lý Gauss-Markov
- Độ bất định của từng hệ số phụ thuộc vào điều kiện của (XᵀX)

### 9.4 Trường hợp ma trận kém điều kiện

Nếu `XᵀX` gần singular (do multicollinearity), dùng **Ridge Regression**:

```
θ̂_ridge = (XᵀX + λI)⁻¹ XᵀY
```

Trong đó λ > 0 là tham số regularization.

> **Lưu ý cho repo này:** phần triển khai hiện tại **không dùng Ridge làm baseline**. Baseline chính thức dùng `numpy.linalg.lstsq` để giữ diễn giải OLS nhất quán với covariance, confidence interval và so sánh tham số thật.

### 9.5 Recursive Least Squares (RLS) – cho dữ liệu streaming

Khi dữ liệu đến theo thời gian thực, dùng RLS để cập nhật θ̂ không cần tính lại toàn bộ:

```
K(t)   = P(t-1)φ(t) / [1 + φ(t)ᵀP(t-1)φ(t)]
θ̂(t)  = θ̂(t-1) + K(t)[y(t) - φ(t)ᵀθ̂(t-1)]
P(t)   = [I - K(t)φ(t)ᵀ] P(t-1)
```

---

## 10. Dự đoán đầu ra

### 10.1 One-step-ahead prediction

Sau khi có θ̂, dự đoán 1 bước trước:

```
ŷ(t|t-1) = φ(t)ᵀ θ̂ = X θ̂
```

Kết quả: `Ŷ = X θ̂`

### 10.2 Multi-step-ahead prediction (Free-run simulation)

Để dự đoán nhiều bước trước (quan trọng cho điều khiển), dùng **simulation mode**: thay y(t-1) và y(t-2) bằng các giá trị **dự đoán** trước đó:

```
ŷ(t) = a₁·ŷ(t-1) + a₂·ŷ(t-2) + [input terms...]
```

> **Chú ý:** Simulation error thường lớn hơn 1-step prediction error, nhưng phản ánh đúng hơn khả năng thực của mô hình.

---

## 11. Đánh giá mô hình

### 11.1 Root Mean Square Error (RMSE)

```
RMSE = sqrt(1/N · Σₜ (y(t) - ŷ(t))²)
```

- Đơn vị: cùng với y(t) (ví dụ: %)
- **Tốt:** RMSE < 1-2% (tùy ứng dụng)
- Nhạy cảm với outliers

### 11.2 Mean Absolute Error (MAE)

```
MAE = 1/N · Σₜ |y(t) - ŷ(t)|
```

- Robust hơn RMSE với outliers
- Dễ giải thích hơn

### 11.3 Fit Percentage (NRMSE-based)

```
FIT = 100 × (1 - ||y - ŷ|| / ||y - ȳ||)
```

Trong đó ȳ = mean(y).

- **FIT = 100%:** Dự đoán hoàn hảo
- **FIT = 0%:** Mô hình chỉ dự đoán giá trị trung bình (không tốt hơn baseline)
- **FIT < 0%:** Mô hình tệ hơn baseline
- **Mục tiêu:** FIT > 80% cho ứng dụng thực tế

### 11.4 R² Score (Coefficient of Determination)

```
R² = 1 - SS_res / SS_tot
   = 1 - Σ(y - ŷ)² / Σ(y - ȳ)²
```

- R² = 1: hoàn hảo
- R² = 0: chỉ bằng mean prediction
- **Mục tiêu:** R² > 0.90

### 11.5 Akaike Information Criterion (AIC)

```
AIC = N·ln(σ̂²) + 2k
```

Trong đó:
- σ̂² = (1/N)·||Y - Ŷ||² (variance của residual)
- k = số tham số = 14
- N = số mẫu dữ liệu

**Dùng AIC để so sánh các cấu trúc mô hình khác nhau** (ARX(1,1,1) vs ARX(2,2,1) vs ARX(3,2,1)...). **AIC nhỏ hơn = mô hình tốt hơn.**

### 11.6 Bayesian Information Criterion (BIC)

```
BIC = N·ln(σ̂²) + k·ln(N)
```

BIC phạt complexity mạnh hơn AIC → thường chọn mô hình đơn giản hơn.

### 11.7 Bảng kết quả mẫu

| Metric | Validation (1-step) | Validation/Test (free-run) | Đánh giá |
|---|---|---|---|
| RMSE | Càng thấp càng tốt | Càng thấp càng tốt | So với baseline và theoretical ceiling |
| FIT | ≥ 85% thường là tốt | Phụ thuộc động học + mức nhiễu | Không được tự suy diễn từ train metrics |
| R² | ≥ 0.92 thường là tốt | Càng cao càng tốt | Phải đi cùng residual diagnostics |

> **Khi dùng synthetic data:** nếu free-run của mô hình gần với free-run của **true parameters**, đó là dấu hiệu tốt hơn việc ép FIT đạt một ngưỡng tuyệt đối.

---

## 12. Chiến lược phân chia dữ liệu

### 12.1 Phân chia tập dữ liệu

```
┌────────────────────────────────────────────────────────────────┐
│                          Full Dataset                          │
│                                                                │
│   DS1 (Train, 60%)   │   DS2 (Valid, 20%)   │   DS3 (Test, 20%) │
└────────────────────────────────────────────────────────────────┘
```

**Cách phân chia baseline cho repo hiện tại:**
- Dùng **phân chia tuần tự theo thời gian** (không shuffle)
- DS1: 60% mẫu đầu tiên để fit tham số
- DS2: 20% mẫu tiếp theo để đánh giá và chọn cấu trúc tham khảo
- DS3: 20% mẫu cuối để kiểm tra khả năng tổng quát hóa cuối cùng

> **Không dùng random split** cho time series vì sẽ gây **data leakage** (thông tin tương lai rò rỉ vào training).

### 12.2 Cross-Validation cho Time Series

Dùng **Time Series Split** (Rolling Origin):

```
Fold 1: Train [1..T₁]    → Test [T₁+1..T₁+h]
Fold 2: Train [1..T₂]    → Test [T₂+1..T₂+h]
...
```

### 12.3 Yêu cầu tối thiểu dữ liệu

| Giai đoạn | Số mẫu tối thiểu | Ghi chú |
|---|---|---|
| Prototype | 500 mẫu | Đủ để estimate cơ bản |
| Development | 2,000 mẫu | Khuyến nghị |
| Production | 10,000+ mẫu | Tốt nhất |

---

## 13. Quy trình chuẩn bị dữ liệu

### 13.1 Data Collection Checklist

- [ ] Xác định sampling period T_s (phút)
- [ ] Đảm bảo tất cả sensors hoạt động đồng bộ
- [ ] Lưu timestamp cho mỗi mẫu
- [ ] Thu thập dữ liệu trong toàn bộ điều kiện vận hành (ngày/đêm, mùa khô/mưa)

### 13.2 Data Cleaning

```python
# Bước 1: Loại bỏ NaN
df.dropna(inplace=True)

# Bước 2: Loại bỏ outliers (z-score > 3)
from scipy import stats
z_scores = np.abs(stats.zscore(df))
df = df[(z_scores < 3).all(axis=1)]

# Bước 3: Kiểm tra khoảng giá trị hợp lý
assert df['Soil_Moisture'].between(0, 100).all()
assert df['Temperature'].between(0, 60).all()
assert df['Humidity'].between(0, 100).all()
```

### 13.3 Normalization / Scaling

**Khuyến nghị cho baseline trong repo:** **không chuẩn hóa** khi fit ARX(2,2,1) synthetic này, vì mục tiêu là giữ hệ số ở đơn vị vật lý gốc và so sánh trực tiếp với `true_params`.

Nếu chuyển sang dữ liệu thực nhiều cảm biến hơn hoặc bài toán regularized identification, có thể chuẩn hóa inputs như sau:

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)   # Fit trên training
X_val_scaled = scaler.transform(X_val)     # Transform validation (KHÔNG fit lại)
```

> **Lưu ý:** nếu chuẩn hóa y hoặc dùng Ridge / Lasso, phải đổi luôn cách diễn giải tham số và uncertainty. Không nên trộn pipeline regularized với cách giải thích kiểu OLS chuẩn.

### 13.4 Persistent Excitation Check

Để đảm bảo dữ liệu đủ phong phú cho nhận dạng tham số:

```python
# Kiểm tra rank của regression matrix
rank_X = np.linalg.matrix_rank(X)
print(f"Rank of X: {rank_X} (phải = 14)")

# Kiểm tra condition number
cond = np.linalg.cond(X.T @ X)
print(f"Condition number: {cond:.2f} (nên < 1000)")
```

### 13.5 Checklist cho dữ liệu synthetic "giống thực tế"

Nếu chưa có dữ liệu thực và phải sinh dữ liệu giả để kiểm thử pipeline, nên đảm bảo các nguyên tắc sau:

- Có **ngưỡng điều khiển** rõ ràng cho `Soil Moisture` thay vì bật/tắt actuator hoàn toàn ngẫu nhiên
- Dùng **hysteresis** (`low_sp`, `high_sp`) để tránh bật/tắt liên tục quanh một ngưỡng duy nhất
- Có **dwell time / minimum on-off time** cho `Drip`, `Mist`, `Fan`
- Có **chu kỳ ngày/đêm** cho `Light`, `Temperature`, `Humidity`
- Có **quán tính** của `Soil Moisture`: đất không tăng/giảm quá mạnh trong 1 mẫu
- `Drip` phải có tác động **mạnh nhưng trễ**, `Mist` tác động **gián tiếp**, `Fan` tác động **làm khô**
- Giữ giá trị trong **range hợp lý**:
  - `Soil Moisture`: thường 10-100%
  - `Temperature`: thường 10-50 °C trong mô phỏng nhà kính
  - `Humidity`: 20-100%
  - `Light`: 0-1500 lux hoặc dải phù hợp với loại cảm biến đang mô phỏng
- Hạn chế `manual override` ngẫu nhiên; nếu có thì tần suất phải thấp và nên vẫn tôn trọng ràng buộc an toàn
- Bộ ngưỡng nên gắn với:
  - loại cây
  - giai đoạn sinh trưởng
  - loại giá thể/đất
  - khí hậu địa phương

> **Lưu ý:** dữ liệu synthetic chỉ nên dùng để kiểm thử thuật toán, debug pipeline và kiểm tra tính đúng của code. Không nên dùng làm bằng chứng duy nhất rằng mô hình sẽ hoạt động tốt ngoài thực địa.

---

## 14. Hướng dẫn triển khai Python

### 14.1 Cài đặt thư viện

```bash
pip install numpy pandas scikit-learn matplotlib scipy
```

### 14.2 Cách dùng nhanh

Nếu bạn chỉ muốn chạy pipeline nhanh, thứ tự nên là:

1. Chuẩn bị `greenhouse_data.csv` theo format ở mục 14.5
2. Đọc dữ liệu bằng `load_greenhouse_data()`
3. Tạo ma trận hồi quy bằng `build_regression_matrix()`
4. Ước lượng tham số bằng `estimate_arx_ls()`
5. Chạy toàn bộ quy trình bằng `run_arx_pipeline()`
6. Xem metrics và file `arx_results.png`

**Đầu vào tối thiểu:**

- `Timestamp`
- `Soil_Moisture`
- `Temperature`
- `Humidity`
- `Light`
- `Drip`
- `Mist`
- `Fan`

**Đầu ra chính của pipeline:**

- `theta`: vector tham số ước lượng
- `train_metrics`, `val_metrics`: các chỉ số đánh giá
- `arx_results.png`: biểu đồ dự đoán và phần dư

### 14.3 Code đầy đủ ARX(2,2,1)

> **Ghi chú đồng bộ repo:** phần code đầy đủ dưới đây mang tính minh họa. Phần triển khai đang dùng thật trong repo đã được tách sang `arx_pipeline.py`, có thêm:
> - split tuần tự `60% / 20% / 20%`
> - metrics cho `1-step`, `12-step`, `free-run`
> - residual diagnostics đầy đủ (Shapiro, D'Agostino, Ljung-Box, input cross-correlation)
> - so sánh với `true_params` và theoretical deterministic free-run ceiling

Trước khi xem code, đây là vai trò của từng hàm:

| Hàm | Vai trò |
|---|---|
| `load_greenhouse_data()` | Đọc và sắp xếp dữ liệu theo thời gian |
| `build_regression_matrix()` | Tạo ma trận đặc trưng từ các lag |
| `estimate_arx_ls()` | Ước lượng tham số bằng Least Squares |
| `compute_metrics()` | Tính RMSE, MAE, Fit%, R² |
| `run_arx_pipeline()` | Ghép toàn bộ quy trình train/validation |
| `plot_results()` | Vẽ đồ thị đầu ra, dự đoán, residuals |

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import r2_score

# ================================================================
# BỘ 1: ĐỌC VÀ CHUẨN BỊ DỮ LIỆU
# ================================================================
def load_greenhouse_data(filepath):
    """
    Đọc dữ liệu nhà kính từ CSV.
    Columns: Timestamp, Soil_Moisture, Temperature, Humidity,
              Light, Drip, Mist, Fan
    """
    df = pd.read_csv(filepath, parse_dates=['Timestamp'])
    df = df.sort_values('Timestamp').reset_index(drop=True)
    df.dropna(inplace=True)
    return df


# ================================================================
# BỘ 2: XÂY DỰNG MA TRẬN HỒI QUY
# ================================================================
def build_regression_matrix(df, na=2, nb=2, nk=1):
    """
    Xây dựng ma trận X và vector Y cho ARX(na, nb, nk).
    
    Parameters:
        df:  DataFrame với columns [Soil_Moisture, Temperature,
              Humidity, Light, Drip, Mist, Fan]
        na:  AR order (số lags của output)
        nb:  Input order (số lags của mỗi input)
        nk:  Input delay (bước trễ của input)
    
    Returns:
        X: regression matrix (N_eff × (na + n_inputs*nb))
        Y: output vector (N_eff,)
    """
    y    = df['Soil_Moisture'].values
    Temp = df['Temperature'].values
    Humi = df['Humidity'].values
    Ligh = df['Light'].values
    Drip = df['Drip'].values
    Mist = df['Mist'].values
    Fan  = df['Fan'].values

    inputs = [Temp, Humi, Ligh, Drip, Mist, Fan]
    n_inputs = len(inputs)
    
    # Số hàng hợp lệ (bỏ qua max_lag mẫu đầu)
    max_lag = max(na, nb + nk - 1)
    N = len(y)
    N_eff = N - max_lag

    # Khởi tạo ma trận
    n_params = na + n_inputs * nb  # 2 + 6*2 = 14
    X = np.zeros((N_eff, n_params))
    Y = np.zeros(N_eff)

    for i in range(N_eff):
        t = i + max_lag  # thời gian thực (index trong df)
        row = []
        
        # AR terms: y(t-1), y(t-2)
        for lag in range(1, na + 1):
            row.append(y[t - lag])
        
        # eXogenous terms: uᵢ(t-nk), uᵢ(t-nk-1), ...
        for u in inputs:
            for lag in range(nk, nk + nb):
                row.append(u[t - lag])
        
        X[i, :] = row
        Y[i]    = y[t]

    return X, Y


# ================================================================
# BỘ 3: ƯỚC LƯỢNG THAM SỐ (LEAST SQUARES)
# ================================================================
def estimate_arx_parameters(X, Y):
    """
    Ước lượng tham số bằng Ordinary Least Squares.
    
    θ̂ = (XᵀX)⁻¹ XᵀY
    
    Returns:
        theta: vector tham số (14,)
        cov:   ma trận covariance của θ̂
    """
    # Dùng numpy lstsq (ổn định hơn inversion trực tiếp)
    theta, residuals, rank, sv = np.linalg.lstsq(X, Y, rcond=None)
    
    # Tính covariance
    N, k = X.shape
    Y_pred = X @ theta
    sigma2 = np.sum((Y - Y_pred)**2) / (N - k)
    
    # Pseudo-inverse để tính covariance
    XtX_inv = np.linalg.pinv(X.T @ X)
    cov = sigma2 * XtX_inv
    
    return theta, cov, sigma2


# ================================================================
# BỘ 4: TÍNH CÁC METRICS
# ================================================================
def compute_metrics(Y_true, Y_pred, n_params, N=None):
    """Tính RMSE, MAE, FIT, R², AIC, BIC."""
    if N is None:
        N = len(Y_true)
    
    residuals = Y_true - Y_pred
    sigma2 = np.mean(residuals**2)
    
    rmse = np.sqrt(sigma2)
    mae  = np.mean(np.abs(residuals))
    fit  = 100 * (1 - np.linalg.norm(residuals) / 
                       np.linalg.norm(Y_true - np.mean(Y_true)))
    r2   = r2_score(Y_true, Y_pred)
    aic  = N * np.log(sigma2) + 2 * n_params
    bic  = N * np.log(sigma2) + n_params * np.log(N)
    
    return {
        'RMSE': rmse,
        'MAE':  mae,
        'FIT':  fit,
        'R²':   r2,
        'AIC':  aic,
        'BIC':  bic,
        'σ²':   sigma2
    }


# ================================================================
# BỘ 5: PIPELINE ĐẦY ĐỦ
# ================================================================
def run_arx_pipeline(filepath, train_ratio=0.7, na=2, nb=2, nk=1):
    """
    Pipeline hoàn chỉnh: load → split → build → estimate → evaluate.
    """
    print("=" * 60)
    print("ARX Model Training Pipeline")
    print(f"Config: na={na}, nb={nb}, nk={nk}")
    print("=" * 60)
    
    # 1. Load data
    df = load_greenhouse_data(filepath)
    N_total = len(df)
    print(f"\n[1] Total samples: {N_total}")
    
    # 2. Train/Validation split (sequential)
    n_train = int(N_total * train_ratio)
    df_train = df.iloc[:n_train].copy()
    df_val   = df.iloc[n_train:].copy().reset_index(drop=True)
    print(f"    Training:   {len(df_train)} samples (DS1)")
    print(f"    Validation: {len(df_val)} samples (DS2)")
    
    # 3. Build regression matrices
    X_train, Y_train = build_regression_matrix(df_train, na, nb, nk)
    X_val,   Y_val   = build_regression_matrix(df_val,   na, nb, nk)
    print(f"\n[2] Regression matrix X_train: {X_train.shape}")
    print(f"    Rank: {np.linalg.matrix_rank(X_train)} / {X_train.shape[1]}")
    
    # 4. Estimate parameters
    theta, cov, sigma2 = estimate_arx_parameters(X_train, Y_train)
    n_params = len(theta)
    print(f"\n[3] Parameter vector θ ({n_params} params):")
    
    param_names = ['a1', 'a2'] + \
                  [f'b{i}' for i in range(1, 13)]
    for name, val, std in zip(param_names, theta, np.sqrt(np.diag(cov))):
        print(f"    {name:5s} = {val:+.6f}  (±{std:.6f})")
    
    # 5. Predictions
    Y_train_pred = X_train @ theta
    Y_val_pred   = X_val   @ theta
    
    # 6. Evaluate
    train_metrics = compute_metrics(Y_train, Y_train_pred, n_params)
    val_metrics   = compute_metrics(Y_val,   Y_val_pred,   n_params)
    
    print("\n[4] Model Performance:")
    print(f"    {'Metric':8s} | {'DS1 (Train)':>12s} | {'DS2 (Valid)':>12s}")
    print(f"    {'-'*8} | {'-'*12} | {'-'*12}")
    for key in ['RMSE', 'MAE', 'FIT', 'R²', 'AIC', 'BIC']:
        tv = train_metrics[key]
        vv = val_metrics[key]
        unit = '%' if key == 'FIT' else ''
        print(f"    {key:8s} | {tv:+12.4f} | {vv:+12.4f}{unit}")
    
    # 7. Plot
    plot_results(Y_val, Y_val_pred, df_val)
    
    return theta, train_metrics, val_metrics


def plot_results(Y_true, Y_pred, df_val):
    """Vẽ đồ thị kết quả."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    
    t = np.arange(len(Y_true))
    
    # Plot 1: Dự đoán vs Thực tế
    axes[0].plot(t, Y_true,  'b-',  label='Actual Soil Moisture', linewidth=1.2)
    axes[0].plot(t, Y_pred,  'r--', label='ARX Prediction',        linewidth=1.2)
    axes[0].set_ylabel('Soil Moisture (%)')
    axes[0].set_title('ARX(2,2,1) – Validation Set Prediction')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Plot 2: Phần dư (residuals)
    residuals = Y_true - Y_pred
    axes[1].plot(t, residuals, 'g-', linewidth=0.8)
    axes[1].axhline(0, color='k', linestyle='--')
    axes[1].fill_between(t, residuals, 0, alpha=0.3, color='green')
    axes[1].set_ylabel('Residual (%)')
    axes[1].set_title('Prediction Residuals')
    axes[1].grid(True, alpha=0.3)
    
    # Plot 3: Histogram của residuals
    axes[2].hist(residuals, bins=40, color='purple', alpha=0.7,
                 edgecolor='black', density=True)
    from scipy.stats import norm
    mu, std = norm.fit(residuals)
    x = np.linspace(residuals.min(), residuals.max(), 100)
    axes[2].plot(x, norm.pdf(x, mu, std), 'r-', linewidth=2,
                 label=f'Normal fit (μ={mu:.3f}, σ={std:.3f})')
    axes[2].set_xlabel('Residual (%)')
    axes[2].set_ylabel('Density')
    axes[2].set_title('Residual Distribution')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('arx_results.png', dpi=150)
    plt.show()
    print("\n[5] Plot saved to arx_results.png")


# ================================================================
# ENTRY POINT
# ================================================================
if __name__ == "__main__":
    theta, train_m, val_m = run_arx_pipeline(
        filepath='greenhouse_data.csv',
        train_ratio=0.7,
        na=2, nb=2, nk=1
    )
```

### 14.4 Tạo dữ liệu giả để kiểm tra

```python
def generate_synthetic_data(N=2000, T_s=60, seed=42):
    """
    Tạo dữ liệu tổng hợp theo logic nhà kính:
    - Có chu kỳ ngày/đêm
    - Có ngưỡng low/high cho Soil Moisture
    - Có hysteresis và dwell time
    - Có tác động trễ của actuator lên đất

    Mục đích: kiểm tra pipeline ARX.
    Không thay thế cho dữ liệu đo thực tế.
    """
    np.random.seed(seed)

    t = np.arange(N)

    samples_per_day = int(24 * 3600 / T_s)
    hour = (t % samples_per_day) / samples_per_day * 24

    # Môi trường nền
    light_base = np.maximum(0, np.sin((hour - 6) / 12 * np.pi))
    Light = np.where(
        (hour >= 6) & (hour <= 18),
        1000 * light_base + np.random.normal(0, 30, N),
        np.random.normal(10, 5, N)
    )
    Light = np.clip(Light, 0, 1500)

    temp_phase = (hour - 14) / 24 * 2 * np.pi
    Temp = 26 + 6*np.cos(temp_phase) + np.random.normal(0, 0.8, N)
    Humidity = 72 - 12*np.cos(temp_phase) + np.random.normal(0, 2.0, N)
    Humidity = np.clip(Humidity, 30, 100)

    # Actuator states
    Drip = np.zeros(N)
    Mist = np.zeros(N)
    Fan = np.zeros(N)

    # Output: Soil Moisture
    y = np.zeros(N)
    y[0] = 65.0
    y[1] = 64.8

    low_sp = 58.0
    high_sp = 70.0
    min_switch_steps = max(2, int(round(600 / T_s)))  # tối thiểu 10 phút
    last_drip_switch = 0
    low_count = 0

    # True parameters: giữ độ lớn hợp lý, không để đất nhảy quá mạnh sau 1 mẫu
    a1, a2 = 0.92, 0.03
    b_temp_1, b_temp_2 = -0.010, -0.004
    b_humi_1, b_humi_2 =  0.004,  0.002
    b_light_1, b_light_2 = -0.0007, -0.0003
    b_drip_1, b_drip_2 =  0.8, 1.6      # tác động kéo dài, mẫu sau mạnh hơn mẫu đầu
    b_mist_1, b_mist_2 =  0.08, 0.05
    b_fan_1, b_fan_2 =  -0.05, -0.02

    for i in range(2, N):
        # 1. Luật điều khiển
        low_count = low_count + 1 if y[i-1] < low_sp else 0
        drip_can_switch = (i - last_drip_switch) >= min_switch_steps

        if Drip[i-1] < 0.5:
            if low_count >= 2 and drip_can_switch:
                Drip[i] = 1.0
                last_drip_switch = i
            else:
                Drip[i] = 0.0
        else:
            if y[i-1] >= high_sp and drip_can_switch:
                Drip[i] = 0.0
                last_drip_switch = i
            else:
                Drip[i] = 1.0

        if Temp[i-1] > 32 or Humidity[i-1] > 90:
            Fan[i] = 1.0
        elif Temp[i-1] < 28 and Humidity[i-1] < 85:
            Fan[i] = 0.0
        else:
            Fan[i] = Fan[i-1]

        if Temp[i-1] > 30 and Humidity[i-1] < 55:
            Mist[i] = 1.0
        elif Temp[i-1] < 27 or Humidity[i-1] > 65:
            Mist[i] = 0.0
        else:
            Mist[i] = Mist[i-1]

        # 2. Actuator ảnh hưởng môi trường
        Temp[i] -= 2.0 * Fan[i] + 2.5 * Mist[i]
        Humidity[i] += 14.0 * Mist[i] - 5.0 * Fan[i]
        Temp[i] = np.clip(Temp[i], 10, 50)
        Humidity[i] = np.clip(Humidity[i], 20, 100)

        # 3. ARX(2,2,1): mỗi input dùng 2 lag
        y[i] = (
            a1 * y[i-1] + a2 * y[i-2]
            + b_temp_1  * Temp[i-1]     + b_temp_2  * Temp[i-2]
            + b_humi_1  * Humidity[i-1] + b_humi_2  * Humidity[i-2]
            + b_light_1 * Light[i-1]    + b_light_2 * Light[i-2]
            + b_drip_1  * Drip[i-1]     + b_drip_2  * Drip[i-2]
            + b_mist_1  * Mist[i-1]     + b_mist_2  * Mist[i-2]
            + b_fan_1   * Fan[i-1]      + b_fan_2   * Fan[i-2]
            + np.random.normal(0, 0.15)
        )
        y[i] = np.clip(y[i], 10, 100)

    # Create DataFrame
    import pandas as pd
    df = pd.DataFrame({
        'Timestamp':      pd.date_range('2025-01-01', periods=N, freq=f'{T_s}s'),
        'Soil_Moisture':  y,
        'Temperature':    Temp,
        'Humidity':       Humidity,
        'Light':          Light,
        'Drip':           Drip,
        'Mist':           Mist,
        'Fan':            Fan
    })
    
    df.to_csv('greenhouse_data.csv', index=False)
    print(f"Generated {N} samples → greenhouse_data.csv")
    return df


# Chạy với dữ liệu synthetic:
# df = generate_synthetic_data(N=3000)
# theta, train_m, val_m = run_arx_pipeline('greenhouse_data.csv')
```

**Giải thích thêm cho ví dụ trên:**

- Mục tiêu của đoạn code là tạo dữ liệu **hợp lý về mặt điều khiển**, không phải mô phỏng vật lý đầy đủ
- `Drip` không còn bật/tắt ngẫu nhiên hoàn toàn, mà bám theo `low_sp/high_sp`
- `Humidity` có hệ số **dương** trong phương trình ARX vì không khí ẩm hơn thường làm giảm tốc độ bay hơi của đất
- `Drip` được mô tả với ảnh hưởng ở cả `t-1` và `t-2`, trong đó `t-2` có thể mạnh hơn để phản ánh thời gian thấm
- Nếu hệ thống thực tế cho thấy tưới có độ trễ dài hơn, hãy tăng `nk` hoặc chuyển sang cấu trúc linh hoạt hơn thay vì cố ép vào `ARX(2,2,1)`

### 14.5 Format CSV yêu cầu

**Tối thiểu cho pipeline ARX:**

```csv
Timestamp,Soil_Moisture,Temperature,Humidity,Light,Drip,Mist,Fan
2025-01-01 00:00:00,65.2,24.1,72.3,0,0,0,1
2025-01-01 00:01:00,65.1,24.2,72.1,0,0,0,1
2025-01-01 00:02:00,65.0,24.3,71.9,0,1,0,0
...
```

**Có thể mở rộng thêm các cột metadata nếu cần phân tích vận hành:**

```csv
Timestamp,Month,Season,Soil_Moisture,Soil_Low_SP,Soil_High_SP,Temperature,Humidity,Light,Drip,Mist,Fan
2025-03-01 00:00:00,3,spring,65.2,58.0,70.0,24.1,72.3,0,0,0,1
2025-03-01 00:01:00,3,spring,65.0,58.0,70.0,24.3,71.9,0,1,0,0
...
```

Các cột như `Month`, `Season`, `Soil_Low_SP`, `Soil_High_SP` không bắt buộc cho ARX cơ bản, nhưng rất hữu ích để:

- kiểm tra logic điều khiển
- giải thích hành vi bật/tắt actuator
- phân tích theo mùa vụ hoặc theo setpoint

---

## 15. Lựa chọn bậc mô hình (Order Selection)

### 15.1 Cách thử các cấu trúc khác nhau

```python
import itertools

def model_selection(df, na_list=[1,2,3], nb_list=[1,2,3], nk_list=[1,2]):
    """
    So sánh các cấu trúc ARX(na, nb, nk) theo AIC.
    """
    n_train = int(len(df) * 0.7)
    df_train = df.iloc[:n_train]
    df_val   = df.iloc[n_train:].reset_index(drop=True)
    
    results = []
    
    for na, nb, nk in itertools.product(na_list, nb_list, nk_list):
        X_tr, Y_tr = build_regression_matrix(df_train, na, nb, nk)
        X_vl, Y_vl = build_regression_matrix(df_val,   na, nb, nk)
        
        theta, _, _ = estimate_arx_parameters(X_tr, Y_tr)
        Y_vl_pred   = X_vl @ theta
        
        n_params = na + 6 * nb
        m = compute_metrics(Y_vl, Y_vl_pred, n_params)
        
        results.append({
            'na': na, 'nb': nb, 'nk': nk,
            'n_params': n_params,
            **m
        })
    
    results_df = pd.DataFrame(results).sort_values('AIC')
    print("\n=== Model Selection Results ===")
    print(results_df[['na','nb','nk','n_params','RMSE','FIT','R²','AIC','BIC']].to_string(index=False))
    return results_df
```

### 15.2 Nguyên tắc lựa chọn

1. **Tối thiểu AIC/BIC** trên validation set
2. **FIT cao nhất** trên validation set (> 80%)
3. **Không quá phức tạp:** na, nb ≤ 5 thường là đủ
4. **Kiểm tra residuals:** phải gần white noise

---

## 16. Phân tích phần dư (Residual Analysis)

### 16.1 Kiểm tra tính white noise của residuals

```python
from scipy.stats import shapiro, kstest, normaltest
import statsmodels.stats.stattools as sms

def residual_analysis(Y_true, Y_pred, theta, X, max_lag=20):
    """
    Phân tích phần dư đầy đủ.
    """
    residuals = Y_true - Y_pred
    N = len(residuals)
    
    print("\n=== RESIDUAL ANALYSIS ===")
    
    # 1. Kiểm tra phân phối chuẩn
    stat_shapiro, p_shapiro = shapiro(residuals[:1000])  # Shapiro tối đa 5000 mẫu
    print(f"\n1. Shapiro-Wilk test (H0: normal):")
    print(f"   W = {stat_shapiro:.4f}, p = {p_shapiro:.4f}")
    print(f"   {'PASSED (normal)' if p_shapiro > 0.05 else 'FAILED (not normal)'}")
    
    # 2. Kiểm tra autocorrelation của residuals
    from statsmodels.stats.diagnostic import acorr_ljungbox
    lb = acorr_ljungbox(residuals, lags=max_lag, return_df=True)
    print(f"\n2. Ljung-Box test (H0: no autocorrelation):")
    failed_lags = lb[lb['lb_pvalue'] < 0.05]
    if failed_lags.empty:
        print(f"   PASSED: No significant autocorrelation found")
    else:
        print(f"   FAILED: Autocorrelation at lags {failed_lags.index.tolist()}")
    
    # 3. Cross-correlation residuals vs inputs
    print(f"\n3. Residual-Input cross-correlation (should be ~0):")
    col_names = ['Temp', 'Humidity', 'Light', 'Drip', 'Mist', 'Fan']
    for i, col in enumerate(col_names):
        cc = np.corrcoef(residuals, X[:, 2+i*2])[0,1]
        status = 'OK' if abs(cc) < 0.1 else '⚠ HIGH'
        print(f"   Corr(e, {col:10s}) = {cc:+.4f}  [{status}]")
    
    # 4. Mean của residuals
    mu_e = np.mean(residuals)
    print(f"\n4. Mean of residuals: {mu_e:.6f} (should be ~0)")
    
    # 5. Variance
    var_e = np.var(residuals)
    print(f"5. Variance of residuals: {var_e:.6f}")
    
    return residuals
```

### 16.2 Giải thích kết quả residual analysis

| Kiểm tra | Kết quả tốt | Kết quả xấu | Hành động |
|---|---|---|---|
| Shapiro-Wilk | p > 0.05 | p < 0.05 | Kiểm tra outliers |
| Ljung-Box | p > 0.05 với mọi lag | p < 0.05 | Tăng na |
| Cross-correlation | \|corr\| < 0.1 | \|corr\| > 0.1 | Tăng nb/nk |
| Mean ≈ 0 | \|μ\| < 0.01 | \|μ\| > 0.01 | Thêm bias term |

---

## 17. Hạn chế và mở rộng

### 17.1 Hạn chế của ARX(2,2,1)

| Hạn chế | Mô tả | Giải pháp |
|---|---|---|
| **Tuyến tính** | Không mô tả được quan hệ phi tuyến (ví dụ: bốc hơi nước theo mô hình Penman-Monteith) | NARX, Neural Network |
| **Cấu trúc cố định** | na=2, nb=2, nk=1 không thay đổi theo điều kiện | Adaptive ARX, gain scheduling |
| **Độ trễ input dùng chung** | Một giá trị `nk` duy nhất có thể không phù hợp đồng thời cho `Drip`, `Mist`, `Fan`, `Light` | Chọn `nk` từ dữ liệu hoặc dùng delay riêng cho từng input |
| **Không nhiễu màu** | ARX giả định nhiễu là white noise; thực tế đây không phải lúc nào cũng đúng | ARMAX, OE, BJ model |
| **Không xét nhiễu đo** | Measurement noise từ sensors không được mô hình hóa riêng | Kalman filter approach |

### 17.2 Mô hình nâng cao

```
ARX    → ARMAX: A(q)y(t) = B(q)u(t) + C(q)e(t)     [thêm MA noise model]
ARX    → OE:   y(t) = B(q)/F(q)·u(t) + e(t)          [Output Error]
ARX    → BJ:   y(t) = B(q)/F(q)·u(t) + C(q)/D(q)·e(t) [Box-Jenkins, đầy đủ nhất]
ARMAX  → NARX: f(y(t-1),...,u(t-1),...,e(t-1)) = 0   [phi tuyến]
```

### 17.3 Tích hợp với bộ điều khiển

ARX model là cơ sở cho **MPC (Model Predictive Control):**

```
Tối ưu: min Σ [y(t+k) - y_ref]² + λΣ[Δu(t+k)]²
Ràng buộc: y = X·θ̂ (ARX constraint)
          u_min ≤ u ≤ u_max
```

---

## 18. Tài liệu tham khảo

### Sách

1. **Ljung, L.** (1999). *System Identification: Theory for the User* (2nd ed.). Prentice-Hall.
   - Chương 4: ARX models; Chương 7: Parameter estimation

2. **Söderström, T. & Stoica, P.** (1989). *System Identification*. Prentice-Hall.

3. **Box, G.E.P., Jenkins, G.M., & Reinsel, G.C.** (2008). *Time Series Analysis: Forecasting and Control* (4th ed.). Wiley.

### Bài báo

4. **Camacho, E.F. & Bordons, C.** (2004). *Model Predictive Control*. Springer. (Ứng dụng ARX trong MPC)

5. **Akaike, H.** (1974). A new look at the statistical model identification. *IEEE Transactions on Automatic Control*, 19(6), 716-723.

### Thư viện Python

6. `numpy.linalg.lstsq` – Least Squares solver
7. `scipy.stats` – Statistical tests
8. `statsmodels` – Time series analysis, Ljung-Box test
9. `sklearn.metrics` – R² score, MSE

### Online Resources

10. MATLAB System Identification Toolbox documentation – ví dụ về ARX trong thực tế
11. Python `sippy` library – System Identification in PYthon

---

*Tài liệu này được tạo để phục vụ quá trình huấn luyện và triển khai mô hình ARX cho hệ thống nhà kính thông minh. Mọi thắc mắc hoặc đóng góp xin liên hệ nhóm nghiên cứu.*
