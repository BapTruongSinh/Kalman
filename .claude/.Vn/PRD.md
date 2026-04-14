# Tài Liệu Yêu Cầu Sản Phẩm

> [!WARNING]
> **CẦN CON NGƯỜI PHÊ DUYỆT TRƯỚC KHI CHỈNH SỬA**
> Tài liệu này là nguồn sự thật cho những gì chúng ta đang xây dựng.
> Các agent Claude phải ĐỌC tài liệu này để hiểu yêu cầu.
> **Không chỉnh sửa, viết lại, hoặc "cập nhật để phản ánh trạng thái hiện tại" trừ khi con người đã chỉ thị rõ trong cuộc trò chuyện hiện tại.**
> Khi không chắc, hãy giữ nguyên và hỏi lại con người.

---

**Phiên bản**: 1.0
**Trạng thái**: Bản nháp
**Cập nhật lần cuối bởi con người**: [YYYY-MM-DD]
**Product owner**: [Tên]

---

## 1. Tóm Tắt Điều Hành

[3-5 câu. Sản phẩm này là gì? Nó giải quyết vấn đề cốt lõi nào? Người dùng chính là ai? Kết quả mong muốn sau khi sử dụng là gì?]

---

## 2. Phát Biểu Vấn Đề

### 2.1 Tình Hình Hiện Tại

[Mô tả thế giới hiện tại: người dùng đang làm gì khi chưa có sản phẩm này? Họ đang dựa vào công cụ, cách làm tạm, hoặc quy trình thủ công nào?]

### 2.2 Vấn Đề

[Định nghĩa chính xác vấn đề. Có ma sát, sự kém hiệu quả, hoặc nhu cầu chưa được đáp ứng nào? Hãy cụ thể.]

### 2.3 Vì Sao Là Bây Giờ

[Vì sao đây là thời điểm phù hợp để xây dựng sản phẩm này? Điều kiện thị trường, nhu cầu người dùng, công nghệ sẵn có, cơ hội kinh doanh.]

---

## 3. Mục Tiêu & Chỉ Số Thành Công

### 3.1 Mục Tiêu Kinh Doanh

- [Mục tiêu 1: ví dụ, "Giảm 40% ticket hỗ trợ khách hàng liên quan đến onboarding"]
- [Mục tiêu 2]
- [Mục tiêu 3]

### 3.2 Chỉ Số Thành Công

| Chỉ số | Baseline | Mục tiêu | Cách đo |
|--------|----------|----------|---------|
| [ví dụ, Tỷ lệ hoàn tất onboarding] | [0%] | [80%] | [Analytics event] |
| [ví dụ, Thời gian đến giá trị đầu tiên] | [N/A] | [< 5 phút] | [Session recording] |
| [ví dụ, Người dùng hoạt động hằng tuần] | [0] | [500 trong 3 tháng] | [Analytics] |

---

## 4. Chân Dung Người Dùng

### Persona: [Tên, ví dụ, "Alex người quản trị"]

- **Vai trò**: [Chức danh hoặc loại người dùng]
- **Mục tiêu**: [Điều họ muốn hoàn thành]
- **Nỗi đau**: [Những bực bội hiện tại mà sản phẩm này giải quyết]
- **Trình độ kỹ thuật**: [Không kỹ thuật / Trung bình / Developer]
- **Tần suất sử dụng**: [Hằng ngày / Hằng tuần / Thỉnh thoảng]

### Persona: [Tên, ví dụ, "Sam người dùng cuối"]

- **Vai trò**: [Chức danh hoặc loại người dùng]
- **Mục tiêu**: [Điều họ muốn hoàn thành]
- **Nỗi đau**: [Những bực bội hiện tại]
- **Trình độ kỹ thuật**: [Không kỹ thuật / Trung bình / Developer]
- **Tần suất sử dụng**: [Hằng ngày / Hằng tuần / Thỉnh thoảng]

---

## 5. Yêu Cầu Chức Năng

> Yêu cầu được đánh số FR-XXX để agent và test có thể tham chiếu chéo rõ ràng.

### 5.1 [Nhóm tính năng: ví dụ, Xác thực]

- **FR-001**: [Người dùng phải có thể đăng ký bằng email và mật khẩu]
- **FR-002**: [Người dùng phải có thể đăng nhập bằng thông tin đã có]
- **FR-003**: [Người dùng phải có thể đặt lại mật khẩu qua email]
- **FR-004**: [Phiên đăng nhập phải hết hạn sau 30 ngày không hoạt động]

### 5.2 [Nhóm tính năng: ví dụ, Dashboard]

- **FR-010**: [...]
- **FR-011**: [...]

### 5.3 [Nhóm tính năng: ví dụ, Cài đặt]

- **FR-020**: [...]

---

## 6. Yêu Cầu Phi Chức Năng

### Hiệu năng
- [ví dụ, Thời gian phản hồi API < 200ms ở p95 trong tải bình thường]
- [ví dụ, Tải trang ban đầu < 3 giây trên kết nối 4G]

### Bảo mật
- [ví dụ, Bắt buộc xác thực cho mọi endpoint không công khai]
- [ví dụ, Toàn bộ dữ liệu người dùng được mã hóa khi lưu trữ]
- [ví dụ, Có biện pháp giảm thiểu OWASP Top 10]

### Khả năng mở rộng
- [ví dụ, Hệ thống phải hỗ trợ tới 10.000 người dùng đồng thời mà không suy giảm hiệu năng]

### Khả năng truy cập
- [ví dụ, Tuân thủ WCAG 2.1 AA cho toàn bộ giao diện hướng người dùng]

### Hỗ trợ trình duyệt / nền tảng
- [ví dụ, Trình duyệt hiện đại: Chrome 110+, Firefox 110+, Safari 16+, Edge 110+]
- [ví dụ, Responsive trên mobile xuống tới chiều rộng 375px]

### Độ tin cậy
- [ví dụ, SLA uptime 99,5%]
- [ví dụ, Sao lưu tự động mỗi 24 giờ]

---

## 7. Ngoài Phạm Vi (v1.0)

Những phần sau sẽ **không** được xây dựng trong phiên bản đầu tiên. Danh sách này ngăn scope creep và giúp agent tránh xây các tính năng chưa cần.

- [Tính năng A - lý do: quá phức tạp cho v1, dự kiến cho v2]
- [Tính năng B - lý do: cần tích hợp bên thứ ba chưa được đánh giá]
- [Tính năng C - lý do: nhu cầu người dùng thấp, đã hạ ưu tiên]

---

## 8. Câu Hỏi Mở

> Đây là các quyết định chưa được giải quyết và cần con người nhập thông tin trước khi có thể triển khai.

| # | Câu hỏi | Chủ sở hữu | Trạng thái |
|---|---------|------------|------------|
| 1 | [ví dụ, Chọn nhà cung cấp thanh toán nào: Stripe hay Paddle?] | [Product Owner] | Mở |
| 2 | [ví dụ, Chúng ta có hỗ trợ SSO trong v1 không?] | [CTO] | Mở |

---

## 9. Lịch Sử Sửa Đổi

> Chỉ con người ghi vào đây. Agent không chỉnh sửa phần này.

| Ngày | Tác giả | Mô tả thay đổi |
|------|---------|----------------|
| [YYYY-MM-DD] | [Tên] | Bản nháp ban đầu |
