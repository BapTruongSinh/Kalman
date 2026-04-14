"""DRF serializers for the dashboard REST API."""

from rest_framework import serializers

from estimation.models import EvaluationSummary, ExperimentRun, PipelineCycle


class RunListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentRun
        fields = ["id", "name", "run_type", "status", "created_at", "dataset_source"]


class CycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineCycle
        fields = [
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
