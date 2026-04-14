# Rule: Security

## Mục tiêu

Giảm thiểu rủi ro an ninh ngay từ thiết kế và quy trình.

## Quy tắc

- Principle of least privilege.
- Không hardcode secret.
- Validate mọi input từ bên ngoài.
- Sanitize output khi render.
- Kiểm soát file upload và permission.
- Audit dependency và cập nhật CVE quan trọng.
- Ghi log truy vết cho hành động nhạy cảm.

## Verification

- Có đường nào bypass auth/authz không?
- Có dữ liệu nhạy cảm nào đang lộ trong log/response không?
- Có secret nào trong repo không?
- Có abuse scenario nào chưa được chặn?
