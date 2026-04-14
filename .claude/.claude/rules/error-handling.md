# Rule: Error Handling

## Mục tiêu

Lỗi phải được phát hiện, phân loại và xử lý nhất quán.

## Quy tắc

- Fail fast tại điểm sai.
- Không nuốt lỗi (không silent catch).
- Tách lỗi theo cấp:
  - validation
  - business
  - system/infrastructure
- Log có context:
  - request id/trace id
  - input liên quan
  - stack trace (nội bộ)
- Error trả về cho user phải rõ hành động tiếp theo.

## Verification

- Đã cover edge case input thiếu/sai chưa?
- Đã có test cho nhóm lỗi chính chưa?
- Có thông điệp lỗi nào quá chung chung không?
- Có route nào có thể fail im lặng không?
