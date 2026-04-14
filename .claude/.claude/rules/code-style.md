# Rule: Code Style

## Nguyên tắc cốt lõi

- Simplicity first: ưu tiên giải pháp ngắn, rõ, dễ bảo trì.
- Systems > prompts: ưu tiên quy trình và cấu trúc.
- Verification > generation: code sinh ra phải qua kiểm chứng.
- Iteration > perfection: ship nhỏ, verify nhanh, cải tiến liên tục.

## Quy tắc thực thi

- Đặt tên rõ nghĩa, tránh viết tắt khó hiểu.
- Hàm ngắn, một trách nhiệm rõ.
- Tránh duplicated logic.
- Comment chỉ khi cần giải thích ý đồ phức tạp.
- Không “quick fix” che dấu root cause.

## Anti-pattern

- Over-engineering quá sớm.
- Magic number hoặc magic string không giải thích.
- Catch error im lặng.
- “Fix tạm cho chạy” rồi bỏ đó.
