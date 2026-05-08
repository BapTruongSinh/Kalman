"""
Các model Django ORM cho pipeline ước lượng Adaptive Kalman.

Schema được thiết kế ở task #002; xem docs/technical/DATABASE.md để biết đầy đủ.
Tất cả bảng dùng charset utf8mb4 theo cấu hình trong Django DATABASES.
"""

from django.conf import settings
from django.db import models


class ExperimentRun(models.Model):
    """
    Mỗi row là một lần chạy live/online estimation.
    Đây là bảng gốc để liên kết toàn bộ dữ liệu liên quan.
    """

    class RunType(models.TextChoices):
        LIVE = "live", "Live"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        ABORTED = "aborted", "Aborted"

    name = models.CharField(max_length=255)
    run_type = models.CharField(
        max_length=20,
        choices=RunType.choices,
        default=RunType.LIVE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    dataset_source = models.CharField(
        max_length=512,
        null=True,
        blank=True,
        help_text="Live source, device, or deployment description for this run",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="experiment_runs",
        help_text="User allowed to POST live samples for this run (live ingestion only)",
    )

    class Meta:
        db_table = "experiment_runs"
        constraints = [
            models.CheckConstraint(
                check=models.Q(run_type="live"),
                name="chk_runs_run_type_live",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="idx_runs_status"),
            models.Index(fields=["created_at"], name="idx_runs_created"),
            models.Index(fields=["owner"], name="idx_runs_owner"),
        ]

    def __str__(self) -> str:
        return f"Run #{self.pk} — {self.name} [{self.status}]"


class ExperimentConfig(models.Model):
    """
    Snapshot cấu hình cố định khi tạo run.
    Quan hệ one-to-one với ExperimentRun để đảm bảo có thể tái lập kết quả.
    Giá trị mặc định bám theo runtime live đã chốt trong ADR-004.
    """

    run = models.OneToOneField(
        ExperimentRun,
        on_delete=models.CASCADE,
        related_name="config",
    )

    # Tham số khởi tạo Kalman theo default ADR-003.
    x0 = models.FloatField(
        default=0.0,
        help_text="Initial state estimate; set to first observed Soil_Moisture before run starts",
    )
    P0 = models.FloatField(default=1.0, help_text="Initial covariance")
    Q = models.FloatField(default=0.05, help_text="Process noise runtime default")
    R0 = models.FloatField(default=1.0, help_text="Initial measurement noise")
    R_min = models.FloatField(default=0.05, help_text="Lower bound for adaptive R")
    R_max = models.FloatField(default=25.0, help_text="Upper bound for adaptive R")
    alpha = models.FloatField(default=0.95, help_text="EMA smoothing factor for adaptive R")

    # Snapshot JSON đầy đủ để tái lập cấu hình.
    raw_config_json = models.TextField(default="{}")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "experiment_configs"

    def __str__(self) -> str:
        return f"Config for Run #{self.run_id}"


class PipelineCycle(models.Model):
    """
    Mỗi row là một time step đã xử lý trong một run.
    Đây là bảng dữ liệu lõi của pipeline ước lượng.
    Mỗi giá trị đã lọc đều truy vết được về raw measurement,
    dự đoán ARX, thông số nội bộ Kalman và cấu hình qua run_id.
    """

    # Dùng BigAutoField tường minh để khớp migration và DEFAULT_AUTO_FIELD override.
    id = models.BigAutoField(primary_key=True)

    class SliceType(models.TextChoices):
        ONLINE = "online", "Online"

    class SourceType(models.TextChoices):
        LIVE = "live", "Live Sensor"

    class CycleStatus(models.TextChoices):
        OK = "ok", "OK"
        SKIPPED_NO_MEASUREMENT = "skipped_no_measurement", "Skipped — No Measurement"
        ERROR = "error", "Error"

    class PreprocessStatus(models.TextChoices):
        VALID = "valid", "Valid"
        SKIPPED = "skipped", "Skipped"

    class AdaptiveStatus(models.TextChoices):
        R_UPDATED = "R_updated", "R Updated"
        R_SKIPPED = "R_skipped", "R Skipped (no measurement)"
        SKIPPED = "skipped", "Skipped (error path)"

    run = models.ForeignKey(
        ExperimentRun,
        on_delete=models.CASCADE,
        related_name="cycles",
    )
    sample_ts = models.DateTimeField(help_text="Source timestamp from dataset")
    cycle_index = models.IntegerField(help_text="Sequential 0-based index within the run")
    slice_type = models.CharField(max_length=15, choices=SliceType.choices)
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.LIVE,
    )

    # --- Dữ liệu đo thô ---
    raw_soil_moisture = models.FloatField(null=True, blank=True)
    raw_temperature = models.FloatField(null=True, blank=True)
    raw_humidity = models.FloatField(null=True, blank=True)
    raw_light = models.FloatField(null=True, blank=True)
    raw_drip = models.FloatField(null=True, blank=True)
    raw_mist = models.FloatField(null=True, blank=True)
    raw_fan = models.FloatField(null=True, blank=True)

    # --- Trạng thái tiền xử lý ---
    preprocess_status = models.CharField(
        max_length=20,
        choices=PreprocessStatus.choices,
        default=PreprocessStatus.VALID,
    )

    # --- Dự đoán ARX ---
    arx_predicted = models.FloatField(
        null=True,
        blank=True,
        help_text="ARX next-step prediction for Soil_Moisture; NULL if prediction was skipped",
    )

    # --- Thông số nội bộ của Kalman filter ---
    kf_x_prior = models.FloatField(null=True, blank=True, help_text="Prior estimate x^-_k")
    kf_P_prior = models.FloatField(null=True, blank=True, help_text="Prior covariance P^-_k")
    kf_innovation = models.FloatField(null=True, blank=True, help_text="Innovation e_k = z_k - x^-_k")
    kf_R = models.FloatField(null=True, blank=True, help_text="Adaptive R_k at this step")
    kf_K = models.FloatField(null=True, blank=True, help_text="Kalman gain K_k")
    kf_x_posterior = models.FloatField(null=True, blank=True, help_text="Filtered estimate x_k")
    kf_P_posterior = models.FloatField(null=True, blank=True, help_text="Updated covariance P_k")

    # --- Kết quả của adaptive estimator ---
    adaptive_status = models.CharField(
        max_length=20,
        choices=AdaptiveStatus.choices,
        default=AdaptiveStatus.R_UPDATED,
        help_text="Whether adaptive R was updated, skipped, or bypassed",
    )

    # --- Kết quả xử lý cycle ---
    cycle_status = models.CharField(
        max_length=30,
        choices=CycleStatus.choices,
        default=CycleStatus.OK,
    )
    error_message = models.CharField(max_length=512, null=True, blank=True)

    # --- Hiệu năng xử lý ---
    latency_ms = models.FloatField(
        null=True,
        blank=True,
        help_text="Wall-clock time for this Kalman step in milliseconds",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Dedupe tương thích MySQL: partial unique index không ổn định trên vài cấu hình;
    # xem ingest_dedupe_key + uq_cycles_run_ingest_dedupe trong Meta.constraints.
    ingest_dedupe_key = models.CharField(
        max_length=191,
        help_text=(
            "Stable key for DB uniqueness: live=run+UTC timestamp."
        ),
    )

    class Meta:
        db_table = "pipeline_cycles"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "cycle_index"],
                name="uq_cycles_run_index",
            ),
            models.UniqueConstraint(
                fields=["run", "ingest_dedupe_key"],
                name="uq_cycles_run_ingest_dedupe",
            ),
            models.CheckConstraint(
                check=models.Q(slice_type__in=["online"]),
                name="chk_cycles_slice_type",
            ),
            models.CheckConstraint(
                check=models.Q(source_type__in=["live"]),
                name="chk_cycles_source_type",
            ),
            models.CheckConstraint(
                check=models.Q(
                    preprocess_status__in=["valid", "skipped"]
                ),
                name="chk_cycles_preprocess_status",
            ),
            models.CheckConstraint(
                check=models.Q(
                    adaptive_status__in=["R_updated", "R_skipped", "skipped"]
                ),
                name="chk_cycles_adaptive_status",
            ),
            models.CheckConstraint(
                check=models.Q(
                    cycle_status__in=["ok", "skipped_no_measurement", "error"]
                ),
                name="chk_cycles_cycle_status",
            ),
        ]
        indexes = [
            models.Index(fields=["run", "sample_ts"], name="idx_cycles_run_ts"),
            models.Index(fields=["run", "slice_type"], name="idx_cycles_run_slice"),
        ]
        ordering = ["run", "cycle_index"]

    def __str__(self) -> str:
        return f"Cycle #{self.cycle_index} @ {self.sample_ts} [{self.cycle_status}]"


class EvaluationSummary(models.Model):
    """
    Metric tổng hợp cho một run live/online.
    """

    class SliceType(models.TextChoices):
        ONLINE = "online", "Online"

    run = models.ForeignKey(
        ExperimentRun,
        on_delete=models.CASCADE,
        related_name="evaluation_summaries",
    )
    slice_type = models.CharField(max_length=15, choices=SliceType.choices)

    # --- Số lượng sample ---
    n_samples = models.IntegerField(default=0)
    n_valid = models.IntegerField(default=0)
    n_skipped = models.IntegerField(default=0)
    n_error = models.IntegerField(default=0)

    # --- Độ chính xác ARX ---
    rmse_arx = models.FloatField(null=True, blank=True)
    mae_arx = models.FloatField(null=True, blank=True)

    # --- Độ chính xác Kalman ---
    rmse_filtered = models.FloatField(null=True, blank=True)
    mae_filtered = models.FloatField(null=True, blank=True)

    # --- Metric đạt/ngưỡng theo ADR-003 ---
    var_diff_raw = models.FloatField(
        null=True, blank=True,
        help_text="var(diff(raw_soil_moisture))"
    )
    var_diff_filtered = models.FloatField(
        null=True, blank=True,
        help_text="var(diff(kf_x_posterior))"
    )
    variance_reduction = models.FloatField(
        null=True, blank=True,
        help_text="1 - var_diff_filtered / var_diff_raw; must be >= 0.20",
    )
    rmse_ratio = models.FloatField(
        null=True, blank=True,
        help_text="rmse_filtered / rmse_arx; must be <= 1.05",
    )
    mae_ratio = models.FloatField(
        null=True, blank=True,
        help_text="mae_filtered / mae_arx; must be <= 1.05",
    )

    # --- Phân bố trạng thái adaptive ---
    n_r_updated = models.IntegerField(
        default=0,
        help_text="Cycles where adaptive R was updated (R_updated)",
    )
    n_r_skipped = models.IntegerField(
        default=0,
        help_text="Cycles where R update was skipped (no measurement)",
    )
    n_adaptive_skipped = models.IntegerField(
        default=0,
        help_text="Cycles on the error path (adaptive_status=skipped)",
    )

    # --- Độ trễ ---
    latency_mean_ms = models.FloatField(
        null=True,
        blank=True,
        help_text="Mean wall-clock time per Kalman step in milliseconds",
    )
    latency_p95_ms = models.FloatField(
        null=True,
        blank=True,
        help_text="95th-percentile wall-clock time per step in milliseconds",
    )

    # --- Chẩn đoán innovation và adaptive R ---
    innovation_mean = models.FloatField(null=True, blank=True)
    innovation_std = models.FloatField(null=True, blank=True)
    innovation_max_abs = models.FloatField(null=True, blank=True)
    R_mean = models.FloatField(null=True, blank=True)
    R_min_observed = models.FloatField(null=True, blank=True)
    R_max_observed = models.FloatField(null=True, blank=True)
    P_mean = models.FloatField(null=True, blank=True)
    P_max = models.FloatField(null=True, blank=True)

    # --- Cờ pass/fail ---
    pass_variance_reduction = models.BooleanField(
        null=True, blank=True,
        help_text="True if variance_reduction >= 0.20",
    )
    pass_rmse_guardrail = models.BooleanField(
        null=True, blank=True,
        help_text="True if rmse_ratio <= 1.05",
    )
    pass_mae_guardrail = models.BooleanField(
        null=True, blank=True,
        help_text="True if mae_ratio <= 1.05",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evaluation_summaries"
        unique_together = [("run", "slice_type")]

    def __str__(self) -> str:
        return f"Eval [{self.slice_type}] for Run #{self.run_id}"

    @property
    def cycle_success_rate(self) -> float | None:
        """Tỉ lệ cycle xử lý bình thường (n_valid / n_samples)."""
        if self.n_samples == 0:
            return None
        return self.n_valid / self.n_samples

    @property
    def sample_loss_rate(self) -> float | None:
        """Tỉ lệ sample bị skip hoặc lỗi ((n_skipped + n_error) / n_samples)."""
        if self.n_samples == 0:
            return None
        return (self.n_skipped + self.n_error) / self.n_samples

    @property
    def passes_acceptance_gate(self) -> bool | None:
        """True nếu cả ba tiêu chí ADR-003 đều pass, None nếu có flag chưa biết."""
        flags = (
            self.pass_variance_reduction,
            self.pass_rmse_guardrail,
            self.pass_mae_guardrail,
        )
        if any(flag is None for flag in flags):
            return None
        return all(flags)
