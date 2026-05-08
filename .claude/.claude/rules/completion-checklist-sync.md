# Rule: Completion Checkbox Sync

## Bắt buộc

1. Làm xong task nào phải tick ngay task đó trong TODO của project tương ứng: `Kalman/TODO.md` hoặc `MPC/TODO.md`.
2. Làm xong task nào phải cập nhật trạng thái tương ứng trong task file của project đó: `Kalman/.tasks/NNN-*.md` hoặc `MPC/.tasks/NNN-*.md`.
3. Không được để trạng thái text `DONE/PENDING` mà không có checkbox tương ứng.
4. Trước khi báo cáo kết thúc, bắt buộc rà soát lại toàn bộ checkbox trong TODO và task file phạm vi đang làm.

## Chuẩn tick

- Chưa làm: `- [ ]`
- Đã làm: `- [x]`

## Quy tắc kết thúc

- Chỉ được kết luận hoàn tất khi danh sách checkbox trong TODO và task file của project đang làm đã được cập nhật đầy đủ theo tiến độ thực tế.
