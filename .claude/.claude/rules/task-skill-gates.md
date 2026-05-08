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

1. `Kalman/TODO.md` là nguồn task chính của estimator/backend/dashboard; `MPC/TODO.md` là nguồn task chính của controller MPC/AMPC.
2. Mỗi task được theo dõi bằng item trong TODO của project tương ứng và file chi tiết trong `.tasks/` của project đó khi cần.
3. Không yêu cầu tạo plan/discussion workflow hoặc chờ user duyệt plan trước khi tạo/cập nhật task, trừ khi user yêu cầu rõ workflow đó.

## Mapping skill tối thiểu theo nhóm việc

- Mỗi task file nên có frontmatter `required_skills`. Ưu tiên skill local trong `.claude/.claude/skills/` khi có, sau đó mới dùng skill hệ thống.

- Lập kế hoạch / backlog / ADR:
  - `planning`
  - `docs` nếu có cập nhật tài liệu
  - `writing-plans`
- Backend Django/Python:
  - `backend`
  - `quality` nếu task yêu cầu test
  - `django-pro`
  - `python-pro`
  - `backend-dev-guidelines`
- Controller MPC/AMPC:
  - `planning` cho thiết kế package/config
  - `backend` cho solver/adapter/actuator
  - `quality` cho test/simulation/validation
  - `docs` cho guide/onboarding/ADR
- Kiểm tra security:
  - `backend-security-coder`
- Kiểm tra test:
  - `quality`
  - `python-testing-patterns`
- Kiểm tra logic/kiến trúc:
  - `planning`
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
