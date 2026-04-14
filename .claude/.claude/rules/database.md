# Rule: Database

## Mục tiêu

An toàn dữ liệu, migration có kiểm soát, truy vết được thay đổi.

## Quy tắc

- Mọi thay đổi schema phải qua migration có version.
- Không sửa trực tiếp production schema khi chưa có plan.
- Có rollback strategy cho migration quan trọng.
- Đặt constraint rõ:
  - PK/FK
  - unique
  - not null
- Tạo index theo query pattern thực tế.
- Tránh `select *` ở luồng nhạy cảm hiệu năng.

## Verification

- Migration có thể chạy lại ổn định không?
- Có test với dữ liệu mẫu và edge case không?
- Query mới có làm tăng tải đáng kể không?
- Có nguy cơ mất dữ liệu khi rollback không?
