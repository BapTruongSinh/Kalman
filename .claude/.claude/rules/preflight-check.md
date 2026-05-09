# Rule: Preflight Check Trước Mọi Công Việc

## Quy tắc bắt buộc

Trước khi bắt đầu một hành động mới, luôn thực hiện preflight:

1. Đọc nhanh `.claude/.claude/review/REVIEW.md`.
2. Đọc các rule trong `.claude/.claude/rules/`.
3. Đọc `Server/docs/technical/CODEBASE_ONBOARDING.md` cho estimator/backend/dashboard, hoặc `MPC/docs/technical/CODEBASE_ONBOARDING.md` cho controller MPC/AMPC, để nắm kiến trúc hiện tại, luồng xử lý, và xác định file/function/module liên quan trước khi phân tích hay sửa code.
4. Nếu công việc liên quan tới task, đọc TODO và `.tasks/` của project tương ứng: `Kalman/TODO.md` + `Kalman/.tasks/`, hoặc `MPC/TODO.md` + `MPC/.tasks/`.
5. Chọn skill phù hợp trong `.claude/.claude/skills/` hoặc skill hệ thống đã cài.
6. Có thể chọn một hoặc nhiều skills để kết hợp.
7. Xác nhận lại phạm vi và mục tiêu công việc khi yêu cầu còn mơ hồ hoặc có rủi ro lệch ý.

## Mục tiêu

- Tránh làm lại việc đã làm.
- Tránh lệch rule.
- Tăng chất lượng quyết định trước khi thực thi.
- Giảm việc sửa mù bằng cách hiểu kiến trúc và đường đi của code trước khi chạm vào file cụ thể.
