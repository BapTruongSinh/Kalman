"""
Các model Django ORM cho pipeline ước lượng Adaptive Kalman.
"""

from django.conf import settings
from django.db import models


class ExperimentRun(models.Model):
    """
    Mỗi row là một lần chạy offline replay hoặc live estimation.
    Đây là bảng gốc để liên kết toàn bộ dữ liệu liên quan.
    """

    class RunType(models.TextChoices):
        OFFLINE_REPLAY = "offline_replay", "Offline Replay"
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
        default=RunType.OFFLINE_REPLAY,
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
        help_text="CSV path or MySQL table/query description used for this run",
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
    """

    class PreprocessPolicy(models.TextChoices):
        KEEP_LAST = "keep_last", "Keep Last Valid"
        INTERPOLATE = "interpolate", "Interpolate"
        SKIP = "skip", "Skip Update"

    run = models.OneToOneField(
        ExperimentRun,
        on_delete=models.CASCADE,
        related_name="config",
    )

    # Tham số khởi tạo Kalman theo default
    x0 = models.FloatField(
        default=0.0,
        help_text="Initial state estimate; set to first observed Soil_Moisture before run starts",
    )
    P0 = models.FloatField(default=1.0, help_text="Initial covariance")
    Q = models.FloatField(default=0.05, help_text="Process noise; tuned on validation slice")
    R0 = models.FloatField(default=1.0, help_text="Initial measurement noise")
    R_min = models.FloatField(default=0.05, help_text="Lower bound for adaptive R")
    R_max = models.FloatField(default=25.0, help_text="Upper bound for adaptive R")
    alpha = models.FloatField(default=0.95, help_text="EMA smoothing factor for adaptive R")

    # Tỉ lệ chia dữ liệu theo thứ tự thời gian.
    train_ratio = models.FloatField(default=0.60)
    val_ratio = models.FloatField(default=0.20)
    test_ratio = models.FloatField(default=0.20)

    # Bậc mô hình ARX.
    arx_na = models.IntegerField(default=2, help_text="Output lag order")
    arx_nb = models.IntegerField(default=2, help_text="Input lag order")
    arx_nk = models.IntegerField(default=1, help_text="Input delay")

    preprocessing_policy = models.CharField(
        max_length=20,
        choices=PreprocessPolicy.choices,
        default=PreprocessPolicy.KEEP_LAST,
    )

    # Snapshot JSON đầy đủ để tái lập cấu hình.
    raw_config_json = models.TextField(default="{}")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "experiment_configs"

    def __str__(self) -> str:
        return f"Config for Run #{self.run_id}"


class ARXArtifact(models.Model):
    """
    Hệ số model ARX đã train và tóm tắt hiệu năng
    Quan hệ one-to-one với ExperimentRun
    """

    run = models.OneToOneField(
        ExperimentRun,
        on_delete=models.CASCADE,
        related_name="arx_artifact",
    )

    # Bậc ARX dùng khi train.
    na = models.IntegerField()
    nb = models.IntegerField()
    nk = models.IntegerField()

    # Nguồn gốc thời gian của dữ liệu train.
    n_train_samples = models.IntegerField()
    train_start_ts = models.DateTimeField()
    train_end_ts = models.DateTimeField()

    # Model được serialize.
    coefficients_json = models.TextField(
        help_text="JSON array of the full theta coefficient vector"
    )
    input_cols_json = models.TextField(
        help_text="JSON array of input column names used (e.g. Temperature, Humidity, ...)"
    )
    output_col = models.CharField(max_length=100, default="Soil_Moisture")

    # Metric đánh giá train/validation.
    rmse_train = models.FloatField(null=True, blank=True)
    rmse_val = models.FloatField(null=True, blank=True)
    mae_train = models.FloatField(null=True, blank=True)
    mae_val = models.FloatField(null=True, blank=True)

    # Đường dẫn tùy chọn tới file artifact .json đã lưu.
    artifact_path = models.CharField(max_length=512, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "arx_artifacts"

    def __str__(self) -> str:
        return f"ARX({self.na},{self.nb},{self.nk}) for Run #{self.run_id}"


class PipelineCycle(models.Model):
    """
    Mỗi row là một time step đã xử lý trong một run.
    Đây là bảng dữ liệu lõi của pipeline ước lượng.
    Mỗi giá trị đã lọc đều truy vết được về raw measurement,
    dự đoán ARX, thông số nội bộ Kalman và cấu hình qua run_id.
    """

    id = models.BigAutoField(primary_key=True)

    class SliceType(models.TextChoices):
        TRAIN = "train", "Train"
        VALIDATION = "validation", "Validation"
        TEST = "test", "Test"

    class SourceType(models.TextChoices):
        CSV_REPLAY = "csv_replay", "CSV Replay"
        MYSQL_REPLAY = "mysql_replay", "MySQL Replay"
        LIVE = "live", "Live Sensor"

    class CycleStatus(models.TextChoices):
        OK = "ok", "OK"
        SKIPPED_NO_MEASUREMENT = "skipped_no_measurement", "Skipped — No Measurement"
        SKIPPED_INVALID = "skipped_invalid", "Skipped — Invalid"
        ERROR = "error", "Error"

    class PreprocessStatus(models.TextChoices):
        VALID = "valid", "Valid"
        INTERPOLATED = "interpolated", "Interpolated"
        KEPT_LAST = "kept_last", "Kept Last Valid"
        SKIPPED = "skipped", "Skipped"
        INVALID = "invalid", "Invalid"

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
        default=SourceType.CSV_REPLAY,
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
    ingest_dedupe_key = models.CharField(
        max_length=191,
        help_text=(
            "Stable key for DB uniqueness: live=run+UTC timestamp; "
            "replay=run+cycle_index (allows duplicate sample_ts in CSV)."
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
                check=models.Q(slice_type__in=["train", "validation", "test"]),
                name="chk_cycles_slice_type",
            ),
            models.CheckConstraint(
                check=models.Q(source_type__in=["csv_replay", "mysql_replay", "live"]),
                name="chk_cycles_source_type",
            ),
            models.CheckConstraint(
                check=models.Q(
                    preprocess_status__in=["valid", "interpolated", "kept_last", "skipped", "invalid"]
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
                    cycle_status__in=["ok", "skipped_no_measurement", "skipped_invalid", "error"]
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


