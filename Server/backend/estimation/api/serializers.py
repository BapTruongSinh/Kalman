"""DRF serializer cho REST API của dashboard."""

from rest_framework import serializers

from estimation.models import (
    AMPCRecommendation,
    EvaluationSummary,
    ExperimentRun,
    GreenhouseControlProfile,
    PipelineCycle,
)


class RunListSerializer(serializers.ModelSerializer):
    """Danh sách run cho dashboard API; bỏ ``dataset_source`` để tránh lộ path."""

    greenhouse_id = serializers.IntegerField(read_only=True)
    greenhouse_name = serializers.CharField(source="greenhouse.name", read_only=True)

    class Meta:
        model = ExperimentRun
        fields = [
            "id",
            "name",
            "run_type",
            "status",
            "greenhouse_id",
            "greenhouse_name",
            "created_at",
        ]


class CycleSerializer(serializers.ModelSerializer):
    greenhouse_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = PipelineCycle
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
    cycle_success_rate = serializers.SerializerMethodField()
    sample_loss_rate = serializers.SerializerMethodField()
    passes_acceptance_gate = serializers.SerializerMethodField()

    def get_cycle_success_rate(self, obj: EvaluationSummary) -> float | None:
        return obj.cycle_success_rate

    def get_sample_loss_rate(self, obj: EvaluationSummary) -> float | None:
        return obj.sample_loss_rate

    def get_passes_acceptance_gate(self, obj: EvaluationSummary) -> bool:
        return obj.passes_acceptance_gate

    class Meta:
        model = EvaluationSummary
        fields = [
            "slice_type",
            "n_samples",
            "n_valid",
            "n_skipped",
            "n_error",
            "rmse_arx",
            "mae_arx",
            "rmse_filtered",
            "mae_filtered",
            "variance_reduction",
            "rmse_ratio",
            "mae_ratio",
            "pass_variance_reduction",
            "pass_rmse_guardrail",
            "pass_mae_guardrail",
            "n_r_updated",
            "n_r_skipped",
            "n_adaptive_skipped",
            "latency_mean_ms",
            "latency_p95_ms",
            "innovation_mean",
            "innovation_std",
            "cycle_success_rate",
            "sample_loss_rate",
            "passes_acceptance_gate",
        ]


class GreenhouseControlProfileSerializer(serializers.ModelSerializer):
    actuator_configured = serializers.SerializerMethodField()

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
        read_only_fields = [
            "id",
            "greenhouse_id",
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

    def get_actuator_configured(self, obj: GreenhouseControlProfile) -> bool:
        return bool(obj.actuator_url and obj.actuator_bearer_token_env)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        target_low = self._float_value(attrs, "target_low", 55.0)
        target_high = self._float_value(attrs, "target_high", 65.0)
        if not (0.0 <= target_low < target_high <= 100.0):
            raise serializers.ValidationError(
                {"target_band": "target_low and target_high must satisfy 0 <= low < high <= 100."}
            )
        for field in ("crop_kc", "pump_max_seconds", "soft_daily_pump_cap_seconds"):
            if field in attrs and self._float_value(attrs, field, 1.0) <= 0.0:
                raise serializers.ValidationError({field: "Value must be > 0."})
        return attrs

    def _float_value(
        self,
        attrs: dict[str, object],
        field: str,
        default: float,
    ) -> float:
        value = attrs.get(field)
        if value is None and self.instance is not None:
            value = getattr(self.instance, field)
        if value is None:
            value = default
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError(
                {field: "Value must be numeric."}
            ) from exc


class AMPCRecommendationSerializer(serializers.ModelSerializer):
    predicted_soil_moisture = serializers.SerializerMethodField()
    target_band = serializers.SerializerMethodField()
    actuator = serializers.SerializerMethodField()

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

    def get_predicted_soil_moisture(self, obj: AMPCRecommendation) -> list[float]:
        return list(obj.predicted_soil_moisture_json or [])

    def get_target_band(self, obj: AMPCRecommendation) -> dict[str, float]:
        return {"low": obj.target_low, "high": obj.target_high}

    def get_actuator(self, obj: AMPCRecommendation) -> dict[str, object]:
        return {
            "enabled": obj.actuator_enabled,
            "executed": obj.actuator_executed,
            "status": obj.actuator_status,
            "command": obj.actuator_command_json,
            "http_status_code": obj.actuator_http_status_code,
            "alert": obj.actuator_alert,
            "error": obj.actuator_error,
        }
