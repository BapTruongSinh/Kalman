# Rule: API Conventions

## Mục tiêu

API nhất quán, dễ test, dễ review, dễ mở rộng.

## Quy ước

- Dùng resource-based naming.
- Dùng đúng HTTP method theo nghĩa chuẩn.
- Version hóa API khi thay đổi phá vỡ tương thích.
- Response format nhất quán:
  - `success`
  - `data`
  - `error` (khi thất bại)
- Error object cần có `code`, `message`, `details`, `trace_id`.

## Verification

- Endpoint có rõ contract input/output không?
- Status code đúng với nghiệp vụ không?
- Error message có hành động được không?
- Contract có bị generic hoặc mơ hồ không?
