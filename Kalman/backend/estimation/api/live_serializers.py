"""
Serializers for the live sensor ingestion endpoint (Task #010).

LiveSampleSerializer  — validates a single device reading POSTed to
    ``POST /api/ingest/samples/``.

LiveIngestResponseSerializer — documents the 201 response shape.
    (Used for documentation / test assertions; responses are built manually
    in the view to avoid a second serialization pass.)
"""

from __future__ import annotations

import math

from rest_framework import serializers

# Sensor channel names that need non-finite guard.
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
    """Return *value* unchanged, or raise ValidationError for NaN / Inf."""
    if value is None:
        return None
    if not math.isfinite(value):
        raise serializers.ValidationError(
            f"{field_name} must be a finite number; got {value!r}."
        )
    return value


class LiveSampleSerializer(serializers.Serializer):
    """Validate a single live sensor reading from a device.

    Required fields
    ---------------
    run_id:
        Primary key of a live :class:`~estimation.models.ExperimentRun`
        whose ``status`` is ``"running"``.
    timestamp:
        ISO-8601 timestamp from the device (UTC recommended; naive timestamps
        are treated as UTC).

    Optional sensor channels
    ------------------------
    All sensor channels accept ``null`` — the Kalman filter will skip the
    measurement-update step when ``soil_moisture`` is absent or invalid.

    Non-finite values (NaN, Infinity, -Infinity) are rejected with 400 Bad
    Request.  MySQL cannot store them and allowing them through would produce a
    500 at save time.
    """

    run_id = serializers.IntegerField(
        min_value=1,
        help_text="ID of a live ExperimentRun in 'running' status.",
    )
    timestamp = serializers.DateTimeField(
        help_text="ISO-8601 UTC timestamp from the sensor (e.g. 2026-04-14T12:00:00Z).",
    )
    # Primary Kalman channel
    soil_moisture = serializers.FloatField(
        allow_null=True,
        required=False,
        default=None,
        help_text="Soil moisture reading (%). Must be finite or null.",
    )
    # Ancillary channels (stored for traceability; not used by Kalman directly)
    temperature = serializers.FloatField(allow_null=True, required=False, default=None)
    humidity = serializers.FloatField(allow_null=True, required=False, default=None)
    light = serializers.FloatField(allow_null=True, required=False, default=None)
    drip = serializers.FloatField(allow_null=True, required=False, default=None)
    mist = serializers.FloatField(allow_null=True, required=False, default=None)
    fan = serializers.FloatField(allow_null=True, required=False, default=None)

    # ── Per-field finite guards ────────────────────────────────────────────────

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
    """Shape of the 201 Created response from ``POST /api/ingest/samples/``.

    Used in tests and documentation; the view constructs the dict directly.
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
