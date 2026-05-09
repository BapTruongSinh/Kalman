"""
Cấu hình pytest gốc cho backend Kalman.

Set ``DJANGO_SETTINGS_MODULE`` trước khi Django được load, để mọi test module
import Django model, ví dụ ``estimation.run_config.service``, đều thấy settings
đã được cấu hình.

pytest-django được dùng cho các test cần database theo kiểu ``TestCase``.
Các test Python thuần như kalman.filter, kalman.prediction,
kalman.ingestion vẫn chạy được mà không cần setup DB.
"""

import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Giá trị mặc định ổn định cho test suite: nếu local .env đặt
# DJANGO_ENV=production thì DASHBOARD_REQUIRE_AUTH sẽ mặc định bật và làm hỏng
# các APIClient test không xác thực. Biến export trực tiếp trong shell vẫn thắng
# vì ở đây dùng setdefault.
os.environ.setdefault("DJANGO_ENV", "development")
os.environ.setdefault("DASHBOARD_REQUIRE_AUTH", "false")

django.setup()
