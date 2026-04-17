"""DRF serializer cho REST API của dashboard."""

from rest_framework import serializers

from estimation.models import ExperimentRun, PipelineCycle


class RunListSerializer(serializers.ModelSerializer):
    """Danh sách run cho dashboard API; bỏ ``dataset_source`` để tránh lộ path."""

    class Meta:
        model = ExperimentRun
        fields = ["id", "name", "run_type", "status", "created_at"]


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

