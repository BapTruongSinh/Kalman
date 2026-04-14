"""
Django ORM models for the Adaptive Kalman estimation pipeline.

Schema designed in task #002 — see docs/technical/DATABASE.md for full reference.
All tables use utf8mb4 charset (configured in Django DATABASES settings).
"""

from django.db import models


class ExperimentRun(models.Model):
    """
    One row per offline replay or live estimation run.
    The root reference for all associated data.
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

    class Meta:
        db_table = "experiment_runs"
        indexes = [
            models.Index(fields=["status"], name="idx_runs_status"),
            models.Index(fields=["created_at"], name="idx_runs_created"),
        ]

    def __str__(self) -> str:
        return f"Run #{self.pk} — {self.name} [{self.status}]"


class ExperimentConfig(models.Model):
    """
    Frozen configuration snapshot created at run start.
    One-to-one with ExperimentRun. Guarantees full reproducibility.
    Default values match ADR-003 locked defaults.
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

    # Kalman initialization (ADR-003 defaults)
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

    # Chronological split ratios
    train_ratio = models.FloatField(default=0.60)
    val_ratio = models.FloatField(default=0.20)
    test_ratio = models.FloatField(default=0.20)

    # ARX model order
    arx_na = models.IntegerField(default=2, help_text="Output lag order")
    arx_nb = models.IntegerField(default=2, help_text="Input lag order")
    arx_nk = models.IntegerField(default=1, help_text="Input delay")

    preprocessing_policy = models.CharField(
        max_length=20,
        choices=PreprocessPolicy.choices,
        default=PreprocessPolicy.KEEP_LAST,
    )

    # Full JSON snapshot for complete reproducibility
    raw_config_json = models.TextField(default="{}")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "experiment_configs"

    def __str__(self) -> str:
        return f"Config for Run #{self.run_id}"


class ARXArtifact(models.Model):
    """
    Trained ARX model coefficients and performance summary.
    One-to-one with ExperimentRun; created after the train slice ARX retraining.
    """

    run = models.OneToOneField(
        ExperimentRun,
        on_delete=models.CASCADE,
        related_name="arx_artifact",
    )

    # ARX order used for training
    na = models.IntegerField()
    nb = models.IntegerField()
    nk = models.IntegerField()

    # Training data provenance
    n_train_samples = models.IntegerField()
    train_start_ts = models.DateTimeField()
    train_end_ts = models.DateTimeField()

    # Serialized model
    coefficients_json = models.TextField(
        help_text="JSON array of the full theta coefficient vector"
    )
    input_cols_json = models.TextField(
        help_text="JSON array of input column names used (e.g. Temperature, Humidity, ...)"
    )
    output_col = models.CharField(max_length=100, default="Soil_Moisture")

    # Validation metrics
    rmse_train = models.FloatField(null=True, blank=True)
    rmse_val = models.FloatField(null=True, blank=True)
    mae_train = models.FloatField(null=True, blank=True)
    mae_val = models.FloatField(null=True, blank=True)

    # Optional path to saved .json artifact file
    artifact_path = models.CharField(max_length=512, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "arx_artifacts"

    def __str__(self) -> str:
        return f"ARX({self.na},{self.nb},{self.nk}) for Run #{self.run_id}"


class PipelineCycle(models.Model):
    """
    One row per processed time step within a run.
    The core estimation data table.
    Every filtered value is traceable back to its raw measurement,
    ARX prediction, Kalman internals, and configuration via run_id.
    """

    # Explicit BigAutoField so the model matches DEFAULT_AUTO_FIELD override and migration.
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

    # --- Raw measurements ---
    raw_soil_moisture = models.FloatField(null=True, blank=True)
    raw_temperature = models.FloatField(null=True, blank=True)
    raw_humidity = models.FloatField(null=True, blank=True)
    raw_light = models.FloatField(null=True, blank=True)
    raw_drip = models.FloatField(null=True, blank=True)
    raw_mist = models.FloatField(null=True, blank=True)
    raw_fan = models.FloatField(null=True, blank=True)

    # --- Preprocessing ---
    preprocess_status = models.CharField(
        max_length=20,
        choices=PreprocessStatus.choices,
        default=PreprocessStatus.VALID,
    )

    # --- ARX prediction ---
    arx_predicted = models.FloatField(
        null=True,
        blank=True,
        help_text="ARX next-step prediction for Soil_Moisture; NULL if prediction was skipped",
    )

    # --- Kalman filter internals ---
    kf_x_prior = models.FloatField(null=True, blank=True, help_text="Prior estimate x^-_k")
    kf_P_prior = models.FloatField(null=True, blank=True, help_text="Prior covariance P^-_k")
    kf_innovation = models.FloatField(null=True, blank=True, help_text="Innovation e_k = z_k - x^-_k")
    kf_R = models.FloatField(null=True, blank=True, help_text="Adaptive R_k at this step")
    kf_K = models.FloatField(null=True, blank=True, help_text="Kalman gain K_k")
    kf_x_posterior = models.FloatField(null=True, blank=True, help_text="Filtered estimate x_k")
    kf_P_posterior = models.FloatField(null=True, blank=True, help_text="Updated covariance P_k")

    # --- Adaptive estimator outcome ---
    adaptive_status = models.CharField(
        max_length=20,
        choices=AdaptiveStatus.choices,
        default=AdaptiveStatus.R_UPDATED,
        help_text="Whether adaptive R was updated, skipped, or bypassed",
    )

    # --- Cycle outcome ---
    cycle_status = models.CharField(
        max_length=30,
        choices=CycleStatus.choices,
        default=CycleStatus.OK,
    )
    error_message = models.CharField(max_length=512, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pipeline_cycles"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "cycle_index"],
                name="uq_cycles_run_index",
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


class EvaluationSummary(models.Model):
    """
    Aggregated metrics per run per data slice.
    Written once after the replay completes.
    The 'test' slice row is the official ADR-003 acceptance gate.
    """

    class SliceType(models.TextChoices):
        TRAIN = "train", "Train"
        VALIDATION = "validation", "Validation"
        TEST = "test", "Test"

    run = models.ForeignKey(
        ExperimentRun,
        on_delete=models.CASCADE,
        related_name="evaluation_summaries",
    )
    slice_type = models.CharField(max_length=15, choices=SliceType.choices)

    # --- Sample counts ---
    n_samples = models.IntegerField(default=0)
    n_valid = models.IntegerField(default=0)
    n_skipped = models.IntegerField(default=0)
    n_error = models.IntegerField(default=0)

    # --- ARX accuracy ---
    rmse_arx = models.FloatField(null=True, blank=True)
    mae_arx = models.FloatField(null=True, blank=True)

    # --- Kalman accuracy ---
    rmse_filtered = models.FloatField(null=True, blank=True)
    mae_filtered = models.FloatField(null=True, blank=True)

    # --- Good-enough metrics (ADR-003) ---
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
        help_text="1 - var_diff_filtered / var_diff_raw; must be >= 0.20 on test slice",
    )
    rmse_ratio = models.FloatField(
        null=True, blank=True,
        help_text="rmse_filtered / rmse_arx; must be <= 1.05 on test slice",
    )
    mae_ratio = models.FloatField(
        null=True, blank=True,
        help_text="mae_filtered / mae_arx; must be <= 1.05 on test slice",
    )

    # --- Innovation and adaptive R diagnostics ---
    innovation_mean = models.FloatField(null=True, blank=True)
    innovation_std = models.FloatField(null=True, blank=True)
    innovation_max_abs = models.FloatField(null=True, blank=True)
    R_mean = models.FloatField(null=True, blank=True)
    R_min_observed = models.FloatField(null=True, blank=True)
    R_max_observed = models.FloatField(null=True, blank=True)
    P_mean = models.FloatField(null=True, blank=True)
    P_max = models.FloatField(null=True, blank=True)

    # --- Pass/fail flags ---
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
    def passes_acceptance_gate(self) -> bool:
        """True if all three ADR-003 acceptance criteria pass."""
        return bool(
            self.pass_variance_reduction
            and self.pass_rmse_guardrail
            and self.pass_mae_guardrail
        )
