<!-- Slide number: 1 -->
Đề tài
Xây dựng mô hình nhà kính thông minh

SVTH: HOÀNG MINH TRÍ -102230220
            ĐINH CÔNG TRUNG SỸ - 102230211
            NGÔ QUANG SINH – 102230210

NĂM HỌC: 2025 - 2026GVHD: TS HUỲNH HỮU HƯNG

<!-- Slide number: 2 -->

PHẦN 1
DATASET

<!-- Slide number: 3 -->

Hệ thống mô phỏng tổng quát

![image.png](GoogleShape114p15.jpg)
Bức tranh hệ thống

![image.png](GoogleShape109p15.jpg)
Generator không chỉ sinh số ngẫu nhiên mà mô phỏng cả một hệ sinh thái thu nhỏ bao gồm:
Môi trường: Nhiệt độ, Độ ẩm, Ánh sáng.

![image.png](GoogleShape118p15.jpg)
Actuator: Quạt, Phun sương, Tưới nhỏ giọt.

![image.png](GoogleShape119p15.jpg)
Biến mục tiêu: Độ ẩm đất (Soil Moisture).

![image.png](GoogleShape120p15.jpg)

<!-- Slide number: 4 -->

Nguyên tắc thiết kế (Thực tế)

![image.png](GoogleShape126p16.jpg)

![image.png](GoogleShape127p16.jpg)

![image.png](GoogleShape128p16.jpg)

![image.png](GoogleShape137p16.jpg)

![image.png](GoogleShape138p16.jpg)

![image.png](GoogleShape139p16.jpg)
Chu kỳ Ngày/Đêm
Tính Mùa vụ
Quán tính Vật lý
Mô phỏng sự biến thiên ánh sáng và nhiệt độ theo giờ thực tế trong ngày.
Điều chỉnh các ngưỡng biên độ nhiệt ẩm phù hợp với từng mùa trong năm.
Trạng thái môi trường thay đổi liên tục, không nhảy bậc tức thời.

<!-- Slide number: 5 -->

Nguyên tắc thiết kế (Kỹ thuật)

![image.png](GoogleShape145p17.jpg)

![image.png](GoogleShape146p17.jpg)

![image.png](GoogleShape147p17.jpg)

![image.png](GoogleShape156p17.jpg)

![image.png](GoogleShape157p17.jpg)

![image.png](GoogleShape158p17.jpg)
Setpoint linh hoạt
Rule-based Logic
Kích thích (Excitation)
Thay đổi các ngưỡng đích liên tục để ép hệ thống bộc lộ đa dạng đặc tính động học.
Actuator vận hành có quy tắc, đảm bảo mối quan hệ nhân quả rõ ràng cho mô hình học.
Đảm bảo tín hiệu đầu vào đủ "giàu" thông tin để nhận dạng tham số chính xác nhất.

<!-- Slide number: 6 -->

TRUE_PARAMS và ý nghĩa vật lý của từng nhóm hệ số

![](Picture37.jpg)
TRUE_PARAMS là bộ hệ số thật mà generator dùng để sinh ra độ ẩm đất. Chúng định nghĩa chiều tác động và độ mạnh của từng biến.
a1, a2 biểu diễn độ nhớ của đất

b_drip_1, b_drip_2 lớn hơn các hệ số khác vì nhỏ giọt là tác động trực tiếp mạnh nhất lên Soil_Moisture

b_mist_* dương nhưng nhỏ vì phun sương chủ yếu ảnh hưởng gián tiếp

b_fan_* âm vì quạt thúc đẩy khô đi

<!-- Slide number: 7 -->

Setpoint

![image.png](GoogleShape90p13.jpg)
Setpoint là giá trị mục tiêu mà hệ điều khiển muốn duy trì ổn định.

![image.png](GoogleShape85p13.jpg)

![image.png](GoogleShape86p13.jpg)
Biến dự án

![image.png](GoogleShape94p13.jpg)
Sử dụng hai ngưỡng: Soil_Low_SP và Soil_High_SP để tạo dải điều khiển linh hoạt.

![image.png](GoogleShape87p13.jpg)
Quy luật vận hành

![image.png](GoogleShape95p13.jpg)
Dưới ngưỡng thấp: Cần tác động (Tưới).

![image.png](GoogleShape98p13.jpg)
Trong vùng tốt: Không cần tưới thêm.

![image.png](GoogleShape99p13.jpg)

### Notes:

<!-- Slide number: 8 -->

Khái niệm Hysteresis
Hysteresis là cơ chế sử dụng hai ngưỡng giá trị khác nhau cho quá trình bật và tắt thiết bị, tạo ra một "khoảng đệm" logic.

![image.png](GoogleShape86p13.jpg)

![image.png](GoogleShape95p13.jpg)
Chống rung (Anti-Chattering): Ngăn chặn việc thiết bị bật/tắt liên tục khi giá trị đo dao động nhỏ quanh một ngưỡng duy nhất.

![image.png](GoogleShape96p13.jpg)
Bảo vệ thiết bị: Giảm tần suất đóng cắt của các actuator (máy bơm, quạt), giúp kéo dài tuổi thọ hệ thống.

![image.png](GoogleShape97p13.jpg)
Tính thực tế: Mô phỏng chính xác hành vi vận hành của các hệ thống điều khiển công nghiệp thực thụ.

![image.png](GoogleShape98p13.jpg)

<!-- Slide number: 9 -->

Minimum Switching Time

![image.png](GoogleShape86p13.jpg)
Đây là khoảng thời gian tối thiểu bắt buộc phải duy trì giữa hai lần thay đổi trạng thái của các thiết bị chấp hành (actuator).

![](Picture20.jpg)
Tránh hành vi phi thực tế: Các hệ thống cơ khí thực thụ không thể bật/tắt liên tục hàng chục lần trong một giây.

![image.png](GoogleShape97p13.jpg)
Giảm rung điều khiển: Loại bỏ hiện tượng "chattering" khi biến đo dao động cực nhỏ sát ngưỡng Setpoint.

![image.png](GoogleShape98p13.jpg)
Dữ liệu hợp lý: Giúp dataset sinh ra có cấu trúc mượt mà, phục vụ tốt nhất cho quá trình nhận dạng hệ thống ARX.

![image.png](GoogleShape99p13.jpg)

![image.png](GoogleShape85p13.jpg)
Ví dụ vận hành:

![image.png](GoogleShape96p13.jpg)
Quạt vừa bật thì chưa được tắt ngay lập tức, hoặc van tưới vừa mở thì không nên đóng/mở lại liên tục trong vài giây.

<!-- Slide number: 10 -->

Bộ dữ liệu

![](Picture4.jpg)

<!-- Slide number: 11 -->

Phân bố dữ liệu theo tháng

![](Picture2.jpg)

<!-- Slide number: 12 -->

Phân bố dữ liệu theo tháng

![](Picture3.jpg)

<!-- Slide number: 13 -->

PHẦN 2
ARX MODEL

<!-- Slide number: 14 -->

Xây dựng ma trận hồi quy
• Output lags: y(t-1), y(t-2) → 2 cột
• Input lags: uᵢ(t-1), uᵢ(t-2) × 6 inputs → 12 cột
• Tổng: ma trận Φ (N × 14), vector y (N × 1)

![](Picture4.jpg)

<!-- Slide number: 15 -->

Chia tập dữ liệu

![](Picture17.jpg)

![](Picture23.jpg)
Với dữ liệu chuỗi thời gian, random split sẽ gây data leakage — mẫu tương lai lọt vào tập train, làm FIT score cao giả tạo.
Chronological split đảm bảo mô hình không bao giờ nhìn thấy dữ liệu tương lai trong quá trình huấn luyện.

<!-- Slide number: 16 -->

Ước lượng tham số

![](Picture4.jpg)

![](Picture2.jpg)
Φ: ma trận hồi quy (N × 14)
y: vector output thực tế (N × 1)
θ̂: vector 14 tham số ước lượng

<!-- Slide number: 17 -->

Đánh giá mô hình

![](Picture3.jpg)
Nhận xét: ARX(3,1,1) FIT SIM cao hơn ~4% nhưng FIT 1-step giảm 5% → chọn ARX(2,2,1) vì cân bằng tốt hơn

<!-- Slide number: 18 -->

Đánh giá mô hình

![](Picture6.jpg)

<!-- Slide number: 19 -->
PHẦN 3
Xác định quy trình tưới

<!-- Slide number: 20 -->
Quy Trình Tính Toán Tổng Quan

Chuỗi logic chuẩn từ FAO-56 để xác định thời gian tưới chính xác cho nhà kính thông minh:

ET₀
ETc
t
I
Dr
mm/h
mm
giây
mm
mm

Bốc thoát hơi
chuẩn
Bốc thoát hơi
cây trồng
Thời gian
bật bơm
Lượng nước
cần tưới
Cân bằng
nước

A

B

C

D

E

Tính ET₀
Tính ETc
Hiệu chỉnh
Tính TAW/RAW
Cân bằng
Dùng FAO Penman-Monteith từ dữ liệu thờI tiết
Áp dụng hệ số cây trồng Kc
Áp dụng hệ số stress Ks nếu thiếu nước
Xác định kho nước vùng rễ
Cập nhật Dr theo thờI gian

<!-- Slide number: 21 -->
BƯỚC A
Tính ET₀ - Bốc Thoát Hơi Chuẩn

![https://kimi-web-img.moonshot.cn/img/d9-wret.s3.us-west-2.amazonaws.com/6e3d1cd43523311457d89aea412ffc4a69c61822.jpg](Image0.jpg)
Công Thức FAO Penman-Monteith

ET₀ = [0.408Δ(Rn - G) + γ(900/(T+273))u₂(es - ea)] / [Δ + γ(1 + 0.34u₂)]
Đơn vị: mm/h (cho tính toán theo giờ)
Ý Nghĩa Các Tham Số
Rn
Bức xạ thuần
G
Dòng nhiệt đất

MJ/m²/h
MJ/m²/h
Giải Thích Công Thức
T
Nhiệt độ không khí
u₂
Tốc độ gió
°C (độ C)
m/s (ở độ cao 2m)
Tử số: Tổng năng lượng khả dụng (bức xạ) và thành phần động học (gió, độ ẩm)
es-ea
Độ bão hòa hơi nước
Δ
Độ dốc áp suất hơi
kPa (kilopascal)
kPa/°C
Mẫu số: Hệ số hiệu chỉnh nhiệt độ và độ ẩm
γ
Hằng số tâm trắc
kPa/°C (~0.067)
Kết quả: "Nhu cầu bốc thoát hơi chuẩn" của khí quyển - lượng nước bốc hơi từ mặt cỏ tham chiếu

<!-- Slide number: 22 -->
BƯỚC B
Tính ETc - Bốc Thoát Hơi Cây Trồng

![https://kimi-web-img.moonshot.cn/img/cdn11.bigcommerce.com/0474b0c020b35ab5aa0f49227c4d0e6bc53b23a7.JPG](Image0.jpg)
Phương Pháp 1: Đơn Giản (Single Coefficient)

ETc = Kc × ET₀
Kc: Hệ số cây trồng (crop coefficient)
ET₀: Bốc thoát hơi chuẩn (mm/h)
ETc: Bốc thoát hơi cây trồng (mm/h)

Giá Trị Kc Tham Khảo

Rau lá (xà lách, cải)
Cà chua, ớt
Kc = 0.9 - 1.0
Kc = 1.0 - 1.15
Phương Pháp 2: Chi Tiết (Dual Coefficient)

Dưa leo
Hành, tỏi
ETc = (Kcb + Ke) × ET₀
Kc = 0.9 - 1.0
Kc = 0.9 - 1.05
*Giá trị Kc thay đổi theo giai đoạn sinh trưởng
Kcb: Hệ số cây cơ bản
Ke: Hệ số bay hơi đất
Ưu điểm: Phù hợp hơn khi quan tâm hiệu ứng mưa/tưới làm ướt bề mặt đất

<!-- Slide number: 23 -->
BƯỚC C
Hiệu Chỉnh Stress Nước

![https://kimi-web-img.moonshot.cn/img/t4.ftcdn.net/a803527902ffe02c5226c521220ad8fcc4255807.jpg](Image0.jpg)
Khi Cây Bị Thiếu Nước (Stress)

ETc_adj = (Ks × Kcb + Ke) × ET₀
Hoặc dạng đơn giản: ETc_adj = Ks × Kc × ET₀
Ks: Hệ số stress nước
Ks = 1: Cây chưa bị stress, hút nước bình thường

Ý Nghĩa CủA Hiệu Chỉnh
Ks < 1: Cây bị thiếu nước, giảm hút nước
Vật lý: Khi đất khô, cây khó hút nước, stomata đóng lại, giảm transpiration
Mục tiêu: Trong nhà kính thông minh, luôn cố gắng giữ Dr ≤ RAW để Ks = 1, tránh stress.

Sinh lý: Cây tự bảo vệ bằng cách giảm thoát hơi nước để tồn tại
Điều Kiện Áp Dụng Ks
Ứng dụng: Giúp dự đoán chính xác nhu cầu nước thực tế khi đất không đủ ẩm
Chưa stress: Khi Dr ≤ RAW → Ks = 1 (cây hút nước tối đa)
Bắt đầu stress: Khi Dr > RAW → Ks < 1 (cây giảm hút nước)
Stress nặng: Khi Dr gần TAW → Ks giảm mạnh, cây héo

<!-- Slide number: 24 -->

Công Thức và Tính Toán Ks

Công Thức Ks

Ks = (TAW - Dr) / [(1-p) × TAW]
Ví Dụ Tính Ks
Áp dụng khi Dr > RAW

Dữ kiện:
• TAW = 45 mm (tổng nước khả dụng)
TAW: Tổng nước khả dụng (mm)
• p = 0.6 → RAW = 0.6 × 45 = 27 mm
RAW: Nước khả dụng dễ dàng sử dụng (mm) = p × TAW
• Dr = 30 mm (thiếu hụt hiện tại)
Dr: Độ thiếu hụt nước hiện tại (mm)
p: Hệ số thoát nước (depletion factor)

Tính toán:
Vì Dr = 30 mm > RAW = 27 mm
→ Cây đang bị stress
Ks = (TAW - Dr) / [(1-p) × TAW]
= (45 - 30) / [(1-0.6) × 45]
= 15 / 18 = 0.83

Các Trường Hợp CủA Ks

Ks = 1 (Dr ≤ RAW)
Cây hút nước bình thường, chưa stress

=> Ks = 0.83 nghĩa là cây chỉ hút được 83% nước so với khả năng tối đa, ETc giảm 17%.

0 < Ks < 1 (RAW < Dr < TAW)
Cây bắt đầu stress, giảm transpiration

Ks = 0 (Dr ≥ TAW)
Cây héo, không thể hút nước

<!-- Slide number: 25 -->
BƯỚC D
Tính Toán Kho Nước Vùng Rễ

![https://kimi-web-img.moonshot.cn/img/cdn1.botland.store/7bc9a8c89239fb7b53286882ce8ff55cd6639a7e.jpg](Image0.jpg)
TAW - Tổng Nước Khả Dụng

TAW = 1000 × (θFC - θWP) × Zr
θFC: Độ ẩm thể tích ở field capacity(độ ẩm đồng ruộng) (m³/m³)
θWP: Độ ẩm thể tích ở wilting point(điểm héo) (m³/m³)
Zr: Độ sâu vùng rễ (m)
Giá Trị Tham Khảo
TAW: mm (lượng nước cây có thể dùng)

Cát
Thịt nhẹ
θFC ≈ 0.10, θWP ≈ 0.04
θFC ≈ 0.15, θWP ≈ 0.06
RAW - Nước Khả Dụng Dễ Dàng Sử Dụng

Thịt (Silt)
Sét thịt
θFC ≈ 0.32, θWP ≈ 0.15
θFC ≈ 0.35, θWP ≈ 0.23

RAW = p × TAW
*Giá trị p phụ thuộc loại cây (thường 0.3-0.6)
Mối quan hệ: TAW > RAW > 0. TAW là tổng nước tối đa, RAW là ngưỡng an toàn.
p: Hệ số thoát nước
RAW: mm (lượng có thể cạn trước khi stress)

Ý nghĩa: Khi Dr < RAW, cây chưa stress. Khi Dr ≥ RAW, cây bắt đầu stress.

<!-- Slide number: 26 -->

Ví Dụ Cân Bằng Nước Theo Ngày

Dữ Kiện Bài Toán
Bảng Tính Toán Chi Tiết

Dr ban đầu (ngày 0): 20 mm
| Giờ | Dr đầu | ETc | Dr cuối | Trạng thái |
| --- | --- | --- | --- | --- |
| 0 | - | - | 20 | Bình thường |
| 1 | 20 | 5 | 25 | Ngưỡng RAW |
| 2 | 25 | 5 | 30 | Bắt đầu stress |
| 3 | 30 | 4 | 34 | Stress nặng |
ETc mỗi ngày: 5 mm/h
RAW: 25 mm (ngưỡng stress)
Không mưa, không tưới
Ks khi stress: 0.8 (giảm 20%)
*ETc ngày 3 = 5×0.8 = 4 mm (do Ks=0.8)

Kết Luận và Hành Động
Tính Toán Theo Giờ
Giờ 1:
Giờ 1: Cần theo dõi chặt chẽ
Dr₁ = 20 + 5 = 25 mm (bằng RAW)
Giờ 2: Cần tưới ngay, để tránh stress

Giờ 2:
Giờ 3: Cây đã stress nặng, cần tưới gấp
Dr₂ = 25 + 5 = 30 mm (> RAW, bắt đầu stress)

Giờ 3:

Dr₃ = 30 + 5×0.8 = 34 mm (Ks=0.8, stress nặng)

<!-- Slide number: 27 -->
Chuyển Đổi: Từ mm Sang Giây Tưới

Bước 1: Xác Định Lượng Nước Cần Tưới
Bước 3: Đổi Từ Thể Tích Sang ThờI Gian

Inet,i ≈ Dr,i
ti = Vi / (η × Q)
Mục tiêu là nạp lại vùng rễ về gần field capacity( độ ẩm đồng ruông ). Theo FAO, để tránh percolation sâu:
ti: Thời gian bật bơm (giây)
Vi: Thể tích nước cần tưới (L)
Ii ≤ Dr,i
η: Hiệu suất hệ thống (0-1)
Q: Lưu lượng bơm (L/s)

Bước 2: Đổi Từ mm Sang Thể Tích

Công Thức Tổng Hợp
Vi = Inet,i × A

ti = (Inet,i × A) / (η × Q)
Quy đổi FAO: 1 mm trên 1 m² = 1 L
Vi: Thể tích nước cần tưới (L)
Đây chính là công thức cần thiết cho MPC
Inet,i: Độ sâu nước cần tưới (mm)
A: Diện tích tưới hiệu dụng (m²)

<!-- Slide number: 28 -->
Tính Thời Gian

Công Thức Tính Thời Gian

Chiến Lược Tưới
Inet,need,k = max(0, Dr,k - Dtarget)

uk = (A × Inet,need,k) / (η × Q)
Chiến lược 1: Tưới đầy
Dtarget = 0, Inet = Dr (tưới đến field capacity)
Inet,need,k: Lượng nước cần tưới (mm)

Dtarget: Mục tiêu depletion (mm)
Chiến lược 2: Tưới vừa đủ
uk: ThờI gian bật bơm (giây)
Dtarget = RAW/2, Inet = Dr - RAW/2

Chiến lược 3: Tưới tối thiểu
Ví Dụ Tính ThờI Gian
Dtarget = RAW, Inet = Dr - RAW (chỉ khi stress)

Dữ kiện:
• Dr = 30 mm, Dtarget = 10 mm
• A = 1 m², η = 0.85, Q = 0.05 L/s

Tính toán:
Inet = 30 - 10 = 20 mm
uk = (1 × 20) / (0.85 × 0.05)
= 20 / 0.0425 = 470 giây ≈ 7.8 phút

<!-- Slide number: 29 -->
Ví Dụ Tính ThờI Gian Tưới
Dữ Kiện Bài Toán
Kết Quả và Diễn Giải

Diện tích tưới: A = 0.25 m²

Lưu lượng bơm: Q = 0.02 L/s
Thời gian tưới: 62.5 giây ≈ 63 giây
Hiệu suất: η = 0.8 (80%)
Tưới khoảng 1 phút 3 giây để bù 4 mm nước

Dr sau khi tưới
Depletion hiện tại: Dr = 7 mm
Dr mới = 7 - 4 = 3 mm = Dtarget (đạt mục tiêu)
Mục tiêu: Dtarget = 3 mm

Nếu tưới 100 giây?
I = (0.8×0.02/0.25)×100 = 6.4 mm > 4 mm → Thấm sâu, lãng phí
Tính Toán
Bước 1: Lượng nước cần tưới
Kiểm Tra Hiệu Suất
Inet = Dr - Dtarget = 7 - 3 = 4 mm

Lý thuyết: 1L / 0.02L/s = 50 giây
Bước 2: Thể tích nước
Thực tế: 50 / 0.8 = 62.5 giây
V = Inet × A = 4 × 0.25 = 1 L
Mất mát: 12.5 giây (20%) do rò rỉ, phân bố không đều

Bước 3: ThờI gian bơm
t = V / (η × Q) = 1 / (0.8 × 0.02) = 62.5 s

<!-- Slide number: 30 -->
Tích Hợp Vào MPC

![https://kimi-web-img.moonshot.cn/img/www.thermoelectric.com/62945e7fa2cd2a506d0606089564d708f349554b.jpg](Image0.jpg)
Biến Điều Khiển Trong MPC

uk = tk (giây bật bơm)
Biến điều khiển uk là thời gian bật bơm ở bước thờI gian k. MPC sẽ tìm chuỗi uk tối ưu để tối thiểu hóa hàm chi phí.

Phương Trình Trạng Thái
Hàm Chuyển Đổi

Dr,k+1 = Dr,k + ETc,k
- (η × Q / A) × uk

Ik(uk) = (η × Q / A) × uk
Đây là phương trình rất đẹp để bỏ vào MPC!
Ik(uk): Lượng nước tưới (mm) từ uk giây bơm
η × Q / A: Hệ số chuyển đổi từ giây sang mm

Đơn vị: (L/s × s) / m² = L/m² = mm

<!-- Slide number: 31 -->
Mô Hình State-Space cho MPC

Định Nghĩa Biến
Phương Trình State-Space

State (Trạng thái)
State equation:
xk = Dr,k hoặc θk
xk+1 = Axk + Buk + Ddk
Độ thiếu hụt nước hoặc độ ẩm đất

Output equation:
Input (Điều khiển)
yk = Cxk
uk = tk (giây bơm)
ThờI gian bật bơm ở bước k

Disturbance (Nhiễu)
Ma Trận Hệ Thống
dk = ET₀,k, nhiệt độ, RH

A = 1 (hệ số tự hồi quy)
Các yếu tố thờI tiết
Dr tự giảm theo thời gian (do ETc)

B = -η×Q/A (hệ số điều khiển)
Output (Đầu ra)
Ảnh hưởng của tưới đến Dr
yk = độ ẩm đất cảm biến

D = Kc (hệ số nhiễu)
Giá trị đo được từ sensor
Ảnh hưởng của ET₀ đến Dr

<!-- Slide number: 32 -->
Chuyển đổi giữa Dr và Độ ẩm %

![https://kimi-web-img.moonshot.cn/img/www.sparkfun.com/2248da1f99891bda58f3794615ca23e7967766c8.jpg](Image0.jpg)
Chuyển Đổi Giữa Dr và θ

TAW = 1000 × (θFC - θWP) × Zr
Dr = 1000 × (θFC - θ) × Zr
θ: Độ ẩm thể tích hiện tại (m³/m³)
θFC: Độ ẩm field capacity

Quy Trình Trong MPC
θWP: Độ ẩm wilting point
Zr: Độ sâu vùng rễ (m)

Bước 1: Tối ưu trên Dr
MPC tính toán và tối ưu hóa trên biến Dr (mm)

Bước 2: Đổi sang θ
Công Thức Ngược: Từ Dr Sang θ
Sử dụng công thức θ = θFC - Dr/(1000×Zr)

θ = θFC - Dr / (1000 × Zr)

Bước 3: So sánh với cảm biến
Đối chiếu θ tính toán với θ đo được từ sensor
FAO gốc làm trên water depth (Dr) vì nó vật lý hơn. Nhưng có thể đổi qua độ ẩm thể tích để so sánh với cảm biến.

<!-- Slide number: 33 -->
Công Thức Hoàn Chỉnh cho Project

1

5

Mô Hình Nước Vùng Rễ
Nếu Có Stress

Dr,k+1 = Dr,k + ETc,k - Ik(uk)
ETc_adj,k = (Ks,k × Kcb,k + Ke,k) × ET₀,k

2

6

Lượng Tưới Do Bơm
Ràng Buộc An Toàn

Ik(uk) = (η × Q / A) × uk
0 ≤ Dr,k ≤ TAW
RAW = p × TAW
3

ET Cây Trồng (Bản Đơn)

Lưu ý cần thực hiện
ETc,k = Kc,k × ET₀,k
Nếu Dr,k < RAW
→ Chưa cần tưới mạnh

Nếu Dr,k ≥ RAW
4

ET Cây Trồng (Bản Chi Tiết)
→ Cần tưới ngay

ETc,k = (Kcb,k + Ke,k) × ET₀,k

<!-- Slide number: 34 -->
Triển Khai Trong MPC
Quy Trình MPC Thực Tế
Trong MPC, không dùng công thức trực tiếp để chốt luôn mà sẽ thử nhiều giá trị và chọn tối ưu:
Hàm Chi Phí J
1

Thử các giá trị u
u = 0, 10, 20, 30, ... giây

J = Σ(Dr,k - Dtarget)²
+ λ₁Σuk²
+ λ₂Σ(Δuk)²
2

Suy ra I(u)
Tính lượng nước từ mỗi u
3

Cập nhật Dr cho toàn bộ horizon
Dr,k+1, Dr,k+2, ..., Dr,k+N
Số hạng 1: Sai lệch độ ẩm
4

Tính hàm chi phí J
Cost function tổng hợp
Số hạng 2: Chi phí năng lượng
Số hạng 3: Ổn định điều khiển
5

Chọn chuỗi u tối ưu
Chuỗi có cost nhỏ nhất

<!-- Slide number: 35 -->

<!-- Slide number: 36 -->

<!-- Slide number: 37 -->

<!-- Slide number: 38 -->

<!-- Slide number: 39 -->

<!-- Slide number: 40 -->

<!-- Slide number: 41 -->

<!-- Slide number: 42 -->

<!-- Slide number: 43 -->

<!-- Slide number: 44 -->

<!-- Slide number: 45 -->

<!-- Slide number: 46 -->

<!-- Slide number: 47 -->

TRÂN TRỌNG
CẢM ƠN