# Rule: Atomic Task + Skill + Quality Gates

## Mục tiêu

Đảm bảo mọi công việc được chia nhỏ, có skill phù hợp, và có kiểm chứng đầy đủ trước khi báo cáo.

## Quy tắc bắt buộc

1. Mỗi task phải đủ nhỏ để thực hiện nhanh, có đầu vào/đầu ra rõ ràng.
2. Mỗi task phải gắn tối thiểu 1 skill phù hợp với đúng loại việc.
3. Trước khi báo cáo kết quả, bắt buộc đi qua 4 cổng kiểm tra:
   - Logic
   - Nghiệp vụ
   - Security
   - Test chạy thực tế

## Rule bổ sung về hoàn tất danh sách task

1. Không được kết thúc session khi còn task `PENDING` trong task list đang thực thi.
2. Phải thực hiện từ trên xuống dưới theo task list, đánh dấu trạng thái rõ ràng cho từng task.
3. Không được dừng ở giữa và hỏi user "có muốn làm tiếp không" khi vẫn còn task bắt buộc chưa xong.
4. Nếu bị giới hạn context/token khi chưa xong task list, phải tiếp tục ở lần chạy tiếp theo cho đến khi hoàn tất.

## Rule bổ sung về nguồn gốc task

1. `Kalman/TODO.md` là nguồn task chính của dự án.
2. Mỗi task được theo dõi bằng item trong `Kalman/TODO.md` và file chi tiết tương ứng trong `Kalman/.tasks/` khi cần.
3. Không yêu cầu tạo plan/discussion workflow hoặc chờ user duyệt plan trước khi tạo/cập nhật task, trừ khi user yêu cầu rõ workflow đó.

## Mapping skill tối thiểu theo nhóm việc

- Lập kế hoạch nếu user yêu cầu rõ:
  - `writing-plans`
- Backend Django/Python:
  - `django-pro`
  - `python-pro`
  - `backend-dev-guidelines`
- Kiểm tra security:
  - `backend-security-coder`
- Kiểm tra test:
  - `python-testing-patterns`
- Kiểm tra logic/kiến trúc:
  - `software-architecture`

## Tiêu chí pass cho 4 cổng

### 1) Logic
- Luồng xử lý không mâu thuẫn.
- Không tạo side-effect sai ý đồ.

### 2) Nghiệp vụ
- Kết quả đúng với yêu cầu business.
- Không lệch quy tắc domain đã chốt.

### 3) Security
- Input được validate.
- Auth/Authz đúng vai trò.
- Không lộ thông tin nhạy cảm trong response/log.

### 4) Test chạy thực tế
- Có test phù hợp với task.
- Chạy test/kiểm tra runtime thành công trước khi báo cáo.

## Không được báo cáo hoàn thành khi

- Chưa gắn skill cho task.
- Chưa qua 1 trong 4 cổng kiểm tra.
- Chưa có bằng chứng test/check.
- Còn task `PENDING` trong phạm vi đã cam kết thực hiện.
