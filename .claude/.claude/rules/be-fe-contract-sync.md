# Rule: Đồng Bộ Contract BE-FE

## Mục tiêu

Đảm bảo backend và frontend luôn tương thích request/response sau mỗi thay đổi.

## Quy tắc bắt buộc

1. Khi sửa BE có ảnh hưởng API (endpoint, payload, status code, field response):
   - Phải cập nhật FE tương ứng để gửi request đúng và đọc response đúng.
2. Khi sửa FE thay đổi request gửi lên:
   - Phải cập nhật BE serializer/view/service để nhận và validate đúng contract mới.
3. Không được đánh dấu hoàn thành nếu chỉ sửa 1 phía BE hoặc FE mà chưa đồng bộ phía còn lại.

## File bắt buộc cập nhật khi thay đổi contract

- `Server/docs/technical/API.md` hoặc file contract mapping tương ứng trong `Server/docs/technical/`
- `FE/src/lib/api.ts`
- `FE/src/lib/*Api.ts`
- Các page/component FE bị ảnh hưởng
- Serializer/View BE liên quan

## Verification bắt buộc

- Có bảng mapping request/response trước và sau thay đổi.
- Có smoke test end-to-end BE-FE cho các flow chính.
- FE không bị lỗi parse dữ liệu hoặc mismatch field.
- BE không bị lỗi validate do FE gửi payload mới.
