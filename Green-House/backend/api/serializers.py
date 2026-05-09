from __future__ import annotations

from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
    AMPCRecommendation,
    AMPCSchedulerState,
    Alert,
    ControlProfile,
    ControlState,
    Device,
    DeviceCommand,
    DeviceState,
    EstimationCycle,
    EvaluationSummary,
    ExperimentRun,
    Greenhouse,
    GreenhouseControlProfile,
    SensorData,
)


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.get_username()
        return token


class DeviceStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceState
        fields = ["is_on", "desired_on", "last_command", "last_value", "extra", "updated_at"]


class DeviceSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    zone = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    uid = serializers.CharField(source="code", read_only=True)

    class Meta:
        model = Device
        fields = [
            "id",
            "zone",
            "zone_name",
            "name",
            "uid",
            "code",
            "device_type",
            "status",
            "is_enabled",
            "firmware_version",
            "last_seen_at",
            "metadata",
            "state",
        ]

    def get_state(self, obj):
        state, _ = DeviceState.objects.get_or_create(device=obj)
        return DeviceStateSerializer(state).data

    def get_zone(self, obj):
        return getattr(settings, "APP_ZONE_ID", 1)

    def get_zone_name(self, obj):
        return getattr(settings, "APP_ZONE_NAME", "Nhà kính chính")


class SensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorData
        fields = [
            "id",
            "temperature",
            "humidity",
            "light",
            "soil_moisture",
            "payload",
            "recorded_at",
        ]


class GreenhouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Greenhouse
        fields = ["id", "name", "location", "is_active", "notes", "created_at", "updated_at"]


class RunListSerializer(serializers.ModelSerializer):
    greenhouse_id = serializers.IntegerField(read_only=True)
    greenhouse_name = serializers.CharField(source="greenhouse.name", read_only=True, default="")

    class Meta:
        model = ExperimentRun
        fields = ["id", "name", "run_type", "status", "greenhouse_id", "greenhouse_name", "created_at"]


class CycleSerializer(serializers.ModelSerializer):
    greenhouse_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = EstimationCycle
        fields = [
            "greenhouse_id",
            "cycle_index",
            "slice_type",
            "sample_ts",
            "raw_soil_moisture",
            "arx_predicted",
            "kf_x_posterior",
            "kf_innovation",
            "kf_R",
            "latency_ms",
            "preprocess_status",
            "cycle_status",
            "adaptive_status",
        ]


class EvaluationSummarySerializer(serializers.ModelSerializer):
    cycle_success_rate = serializers.FloatField(read_only=True)
    sample_loss_rate = serializers.FloatField(read_only=True)
    passes_acceptance_gate = serializers.BooleanField(read_only=True)

    class Meta:
        model = EvaluationSummary
        fields = [
            "run_id",
            "total_samples",
            "accepted_samples",
            "dropped_samples",
            "success_cycles",
            "failed_cycles",
            "mae_arx_vs_observed",
            "mae_kf_vs_observed",
            "rmse_arx_vs_observed",
            "rmse_kf_vs_observed",
            "avg_latency_ms",
            "p95_latency_ms",
            "max_latency_ms",
            "avg_R",
            "min_R",
            "max_R",
            "cycle_success_rate",
            "sample_loss_rate",
            "passes_acceptance_gate",
        ]


class ControlStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlState
        fields = ["mode", "manual_reason", "manual_changed_at", "updated_at"]


class AMPCSchedulerStateSerializer(serializers.ModelSerializer):
    greenhouse_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = AMPCSchedulerState
        fields = [
            "greenhouse_id",
            "is_enabled",
            "interval_seconds",
            "is_executing",
            "last_started_at",
            "last_stopped_at",
            "last_run_at",
            "next_run_at",
            "last_status",
            "last_error",
            "updated_at",
        ]


class EstimationCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstimationCycle
        fields = [
            "id",
            "sample_ts",
            "cycle_index",
            "run_id",
            "greenhouse_id",
            "slice_type",
            "source_type",
            "validation_status",
            "validation_reason",
            "preprocess_status",
            "cycle_status",
            "adaptive_status",
            "raw_soil_moisture",
            "raw_temperature",
            "raw_humidity",
            "raw_light",
            "raw_drip",
            "raw_mist",
            "raw_fan",
            "arx_predicted",
            "kf_x_prior",
            "kf_P_prior",
            "kf_innovation",
            "kf_x_posterior",
            "kf_P_posterior",
            "kf_R",
            "kf_K",
            "latency_ms",
            "error_message",
            "ingest_dedupe_key",
        ]


class ControlProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlProfile
        fields = [
            "crop_name",
            "crop_kc",
            "target_low",
            "target_high",
            "step_seconds",
            "horizon_steps",
            "pump_min_seconds",
            "pump_max_seconds",
            "pump_grid_seconds",
            "soft_daily_pump_cap_seconds",
            "weight_band",
            "weight_water",
            "weight_switch",
            "weight_daily",
            "weight_terminal",
            "adaptive_enabled",
            "adaptive_bias_window",
            "adaptive_max_abs_bias",
            "stale_after_seconds",
            "actuator_enabled",
            "updated_at",
        ]

    def validate(self, attrs):
        target_low = attrs.get("target_low", getattr(self.instance, "target_low", 55.0))
        target_high = attrs.get("target_high", getattr(self.instance, "target_high", 65.0))
        pump_min = attrs.get("pump_min_seconds", getattr(self.instance, "pump_min_seconds", 0.0))
        pump_max = attrs.get("pump_max_seconds", getattr(self.instance, "pump_max_seconds", 300.0))
        pump_grid = attrs.get("pump_grid_seconds", getattr(self.instance, "pump_grid_seconds", 30.0))
        if not (0.0 <= target_low < target_high <= 100.0):
            raise serializers.ValidationError("target_low/target_high must satisfy 0 <= low < high <= 100")
        if pump_min < 0 or pump_max <= pump_min:
            raise serializers.ValidationError("pump_max_seconds must be greater than pump_min_seconds")
        if pump_grid <= 0 or pump_grid > pump_max:
            raise serializers.ValidationError("pump_grid_seconds must be > 0 and <= pump_max_seconds")
        return attrs


class GreenhouseControlProfileSerializer(serializers.ModelSerializer):
    actuator_configured = serializers.BooleanField(read_only=True)

    class Meta:
        model = GreenhouseControlProfile
        fields = [
            "id",
            "greenhouse_id",
            "crop_name",
            "crop_kc",
            "target_low",
            "target_high",
            "pump_max_seconds",
            "soft_daily_pump_cap_seconds",
            "actuator_enabled",
            "step_seconds",
            "horizon_steps",
            "pump_min_seconds",
            "pump_grid_seconds",
            "cost_band_violation",
            "cost_water_use",
            "cost_switching",
            "cost_daily_cap_excess",
            "cost_terminal_band_violation",
            "adaptive_enabled",
            "adaptive_bias_window",
            "adaptive_max_abs_bias",
            "safety_stale_after_seconds",
            "actuator_timeout_seconds",
            "actuator_configured",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "greenhouse_id", "created_at", "updated_at"]

    def validate(self, attrs):
        target_low = attrs.get("target_low", getattr(self.instance, "target_low", 55.0))
        target_high = attrs.get("target_high", getattr(self.instance, "target_high", 65.0))
        pump_min = attrs.get("pump_min_seconds", getattr(self.instance, "pump_min_seconds", 0.0))
        pump_max = attrs.get("pump_max_seconds", getattr(self.instance, "pump_max_seconds", 300.0))
        pump_grid = attrs.get("pump_grid_seconds", getattr(self.instance, "pump_grid_seconds", 30.0))
        if not (0.0 <= target_low < target_high <= 100.0):
            raise serializers.ValidationError("target_low/target_high must satisfy 0 <= low < high <= 100")
        if pump_min < 0 or pump_max <= pump_min:
            raise serializers.ValidationError("pump_max_seconds must be greater than pump_min_seconds")
        if pump_grid <= 0 or pump_grid > pump_max:
            raise serializers.ValidationError("pump_grid_seconds must be > 0 and <= pump_max_seconds")
        return attrs


class AMPCRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AMPCRecommendation
        fields = [
            "id",
            "sensor_data",
            "estimation",
            "device_command",
            "mode",
            "pump_seconds",
            "step_seconds",
            "predicted_soil_moisture",
            "target_band",
            "objective_cost",
            "safety_status",
            "reason",
            "bias_correction",
            "bias_window_count",
            "used_today_pump_seconds",
            "command_created",
            "actuator_status",
            "config_snapshot",
            "state_snapshot",
            "created_at",
        ]


class LegacyAMPCRecommendationSerializer(serializers.ModelSerializer):
    predicted_soil_moisture = serializers.JSONField()
    target_band = serializers.JSONField()
    actuator = serializers.SerializerMethodField()
    state_cycle_id = serializers.IntegerField(source="estimation_id", read_only=True)
    cost = serializers.FloatField(source="objective_cost", read_only=True)

    class Meta:
        model = AMPCRecommendation
        fields = [
            "id",
            "greenhouse_id",
            "mode",
            "state_cycle_id",
            "run_id",
            "pump_seconds",
            "step_seconds",
            "predicted_soil_moisture",
            "target_band",
            "cost",
            "safety_status",
            "reason",
            "bias_correction",
            "bias_window_count",
            "used_today_pump_seconds",
            "actuator",
            "created_at",
        ]

    def get_actuator(self, obj):
        return {
            "status": obj.actuator_status,
            "command_created": obj.command_created,
            "device_command_id": obj.device_command_id,
        }


class LiveSampleSerializer(serializers.Serializer):
    run_id = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    soil_moisture = serializers.FloatField(required=False, allow_null=True)
    temperature = serializers.FloatField(required=False, allow_null=True)
    humidity = serializers.FloatField(required=False, allow_null=True)
    light = serializers.FloatField(required=False, allow_null=True)
    drip = serializers.FloatField(required=False, allow_null=True)
    mist = serializers.FloatField(required=False, allow_null=True)
    fan = serializers.FloatField(required=False, allow_null=True)


class AlertSerializer(serializers.ModelSerializer):
    zone = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    device_name = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "id",
            "zone",
            "zone_name",
            "device",
            "device_name",
            "level",
            "title",
            "message",
            "is_read",
            "happened_at",
        ]

    def get_zone(self, obj):
        return getattr(settings, "APP_ZONE_ID", 1)

    def get_zone_name(self, obj):
        return getattr(settings, "APP_ZONE_NAME", "Nhà kính chính")

    def get_device_name(self, obj):
        return obj.device.name if obj.device else ""


class DeviceCommandSerializer(serializers.ModelSerializer):
    device_code = serializers.CharField(source="device.code", read_only=True)

    class Meta:
        model = DeviceCommand
        fields = [
            "id",
            "device",
            "device_code",
            "command",
            "value",
            "payload",
            "status",
            "created_at",
            "acked_at",
        ]
