# Rule: Git Workflow

## Mục tiêu

Lịch sử thay đổi rõ ràng, dễ review, dễ rollback.

## Quy tắc

- Branch theo nhiệm vụ rõ nghĩa.
- Commit nhỏ, có ý nghĩa, message rõ.
- PR phải mô tả:
  - mục tiêu
  - phạm vi
  - verification đã chạy
  - risk và rollback note
- Không merge khi chưa qua quality gates.
- Không bỏ qua test nếu là thay đổi hành vi.

## Verification

- Có reproducer hoặc steps check cho issue fix không?
- Có test case cho regression không?
- Reviewer có đủ context để approve không?
