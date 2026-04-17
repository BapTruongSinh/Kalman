"""
Serializer cho endpoint nạp dữ liệu sensor live

LiveSampleSerializer  — validate một sample thiết bị POST lên
    "POST /api/ingest/samples/".

LiveIngestResponseSerializer — mô tả shape response 201.
    (Dùng cho tài liệu / test assertion; view tự build response dict để tránh
    serialize lần thứ hai.)
"""

from __future__ import annotations

import math

from rest_framework import serializers

# Tên các kênh sensor cần chặn giá trị không hữu hạn.
_SENSOR_CHANNELS = (
    "soil_moisture",
    "temperature",
    "humidity",
    "light",
    "drip",
    "mist",
    "fan",
)


def _validate_finite_or_null(value: float | None, field_name: str) -> float | None:
    """Trả lại value nếu hợp lệ, hoặc ném ValidationError nếu là NaN / Inf."""
    if value is None:
        return None
    if not math.isfinite(value):
        raise serializers.ValidationError(
            f"{field_name} must be a finite number; got {value!r}."
        )
    return value


class LiveSampleSerializer(serializers.Serializer):
    """Validate một sample sensor live từ thiết bị.
    """

    run_id = serializers.IntegerField(
        min_value=1,
        help_text="ID of a live ExperimentRun in 'running' status.",
    )
    timestamp = serializers.DateTimeField(
        help_text="ISO-8601 UTC timestamp from the sensor (e.g. 2026-04-14T12:00:00Z).",
    )
    # Kênh chính của Kalman.
    soil_moisture = serializers.FloatField(
        allow_null=True,
        required=False,
        default=None,
        help_text="Soil moisture reading (%). Must be finite or null.",
    )
    # Kênh phụ, lưu để truy vết; Kalman không dùng trực tiếp.
    temperature = serializers.FloatField(allow_null=True, required=False, default=None)
    humidity = serializers.FloatField(allow_null=True, required=False, default=None)
    light = serializers.FloatField(allow_null=True, required=False, default=None)
    drip = serializers.FloatField(allow_null=True, required=False, default=None)
    mist = serializers.FloatField(allow_null=True, required=False, default=None)
    fan = serializers.FloatField(allow_null=True, required=False, default=None)

    # ── Chặn giá trị không hữu hạn theo từng field

    def validate_soil_moisture(self, value: float | None) -> float | None:
        return _validate_finite_or_null(value, "soil_moisture")

    def validate_temperature(self, value: float | None) -> float | None:
        return _validate_finite_or_null(value, "temperature")

    def validate_humidity(self, value: float | None) -> float | None:
        return _validate_finite_or_null(value, "humidity")

    def validate_light(self, value: float | None) -> float | None:
        return _validate_finite_or_null(value, "light")

    def validate_drip(self, value: float | None) -> float | None:
        return _validate_finite_or_null(value, "drip")

    def validate_mist(self, value: float | None) -> float | None:
        return _validate_finite_or_null(value, "mist")

    def validate_fan(self, value: float | None) -> float | None:
        return _validate_finite_or_null(value, "fan")


class LiveIngestResponseSerializer(serializers.Serializer):
    """Shape của response 201 Created từ "POST /api/ingest/samples/".

    Dùng trong test và tài liệu; view tự tạo dict trực tiếp.
    """

    cycle_index = serializers.IntegerField(
        help_text="0-based index of this step within the run.",
    )
    preprocess_status = serializers.CharField(
        help_text="'valid' | 'skipped'.",
    )
    cycle_status = serializers.CharField(
        help_text="'ok' | 'skipped_no_measurement' | 'error'.",
    )
    adaptive_status = serializers.CharField(
        help_text="'R_updated' | 'R_skipped' | 'skipped'.",
    )
    kf_x_posterior = serializers.FloatField(
        allow_null=True,
        help_text="Filtered soil-moisture estimate for this step.",
    )
    kf_innovation = serializers.FloatField(
        allow_null=True,
        help_text="Measurement residual e_k = z_k − x^-_k; null when no update.",
    )
