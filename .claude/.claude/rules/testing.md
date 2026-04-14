# Rule: Testing & Verification

## Tư duy

Never mark done without proof.

## Bắt buộc cho mọi thay đổi

1. Xác định expected behavior.
2. Chạy test phù hợp (unit/integration/smoke).
3. So sánh expected vs actual.
4. Ghi nhận mismatch và sửa đến khi pass.

## Framework 4C

### Correctness
- Logic và output đúng như yêu cầu.

### Completeness
- Đủ case chính và edge case.

### Context-fit
- Đúng với bối cảnh nghiệp vụ và đối tượng.

### Consequence
- Đánh giá rủi ro nếu đưa vào dùng ngay.

## Checklist nhanh

- [ ] Có test case cho happy path
- [ ] Có test case cho input lỗi/edge case
- [ ] Có quan sát log sau thay đổi
- [ ] Có đánh giá regression risk
- [ ] Có cập nhật lesson nếu gặp lỗi lặp lại
