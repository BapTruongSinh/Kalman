-- Tài liệu tham khảo cấu trúc bảng cốt lõi cho dự án hiện tại
-- Bảng thực tế sẽ do Django migrations tạo ra.

CREATE TABLE sensor_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    temperature DECIMAL(5,2) NULL,
    humidity DECIMAL(5,2) NULL,
    light DECIMAL(10,2) NULL,
    soil_moisture DECIMAL(5,2) NULL,
    payload JSON NULL,
    recorded_at DATETIME NOT NULL,
    received_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE device (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    device_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    firmware_version VARCHAR(50) NOT NULL DEFAULT '',
    api_token VARCHAR(64) NOT NULL UNIQUE,
    last_seen_at DATETIME NULL,
    metadata JSON NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
