from __future__ import annotations

import secrets
from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


FAO56_SOIL_PRESETS = {
    'sand': {'theta_fc': 0.10, 'theta_wp': 0.04, 'theta_sat': 0.45},
    'light_loam': {'theta_fc': 0.15, 'theta_wp': 0.06, 'theta_sat': 0.45},
    'loam': {'theta_fc': 0.32, 'theta_wp': 0.15, 'theta_sat': 0.45},
    'clay_loam': {'theta_fc': 0.35, 'theta_wp': 0.23, 'theta_sat': 0.45},
}

FAO56_SOIL_TYPE_CHOICES = [
    (soil_type, soil_type.replace('_', ' ').title())
    for soil_type in FAO56_SOIL_PRESETS
]


class Greenhouse(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='greenhouses',
    )
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'greenhouses'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='uq_greenhouse_owner_name'),
        ]

    def __str__(self):
        return f'{self.name} ({self.owner_id})'


class ExperimentRun(TimeStampedModel):
    class RunType(models.TextChoices):
        LIVE = 'live', 'Live'

    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    name = models.CharField(max_length=120)
    run_type = models.CharField(max_length=20, choices=RunType.choices, default=RunType.LIVE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    dataset_source = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    greenhouse = models.ForeignKey(
        Greenhouse,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='runs',
    )

    class Meta:
        db_table = 'experiment_runs'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.name} ({self.run_type})'


class ExperimentConfig(TimeStampedModel):
    run = models.OneToOneField(ExperimentRun, on_delete=models.CASCADE, related_name='config')
    x0 = models.FloatField(default=0.0)
    P0 = models.FloatField(default=1.0)
    Q = models.FloatField(default=0.01)
    R0 = models.FloatField(default=1.0)
    R_min = models.FloatField(default=0.01)
    R_max = models.FloatField(default=25.0)
    alpha = models.FloatField(default=0.05)
    raw_config_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'experiment_configs'

    def __str__(self):
        return f'Config<{self.run_id}>'


class EvaluationSummary(TimeStampedModel):
    run = models.OneToOneField(ExperimentRun, on_delete=models.CASCADE, related_name='evaluation_summary')
    total_samples = models.PositiveIntegerField(default=0)
    accepted_samples = models.PositiveIntegerField(default=0)
    dropped_samples = models.PositiveIntegerField(default=0)
    success_cycles = models.PositiveIntegerField(default=0)
    failed_cycles = models.PositiveIntegerField(default=0)
    mae_arx_vs_observed = models.FloatField(null=True, blank=True)
    mae_kf_vs_observed = models.FloatField(null=True, blank=True)
    rmse_arx_vs_observed = models.FloatField(null=True, blank=True)
    rmse_kf_vs_observed = models.FloatField(null=True, blank=True)
    avg_latency_ms = models.FloatField(null=True, blank=True)
    p95_latency_ms = models.FloatField(null=True, blank=True)
    max_latency_ms = models.FloatField(null=True, blank=True)
    avg_R = models.FloatField(null=True, blank=True)
    min_R = models.FloatField(null=True, blank=True)
    max_R = models.FloatField(null=True, blank=True)
    acceptance_gate_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'evaluation_summaries'

    @property
    def cycle_success_rate(self) -> float:
        total = self.success_cycles + self.failed_cycles
        return float(self.success_cycles / total) if total else 0.0

    @property
    def sample_loss_rate(self) -> float:
        return float(self.dropped_samples / self.total_samples) if self.total_samples else 0.0

    @property
    def passes_acceptance_gate(self) -> bool:
        return bool(self.acceptance_gate_json.get('passes', False))

    def __str__(self):
        return f'Evaluation<{self.run_id}>'


class Device(TimeStampedModel):
    class DeviceType(models.TextChoices):
        CONTROLLER = 'controller', 'Controller'
        FAN = 'fan', 'Fan'
        PUMP = 'pump', 'Pump'
        LIGHT = 'light', 'Light'
        MIST = 'mist', 'Mist'

    class DeviceStatus(models.TextChoices):
        ONLINE = 'online', 'Online'
        OFFLINE = 'offline', 'Offline'
        ERROR = 'error', 'Error'

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    greenhouse = models.ForeignKey(
        Greenhouse,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='devices',
        db_constraint=False,
    )
    device_type = models.CharField(max_length=20, choices=DeviceType.choices)
    status = models.CharField(
        max_length=20,
        choices=DeviceStatus.choices,
        default=DeviceStatus.OFFLINE,
    )
    is_enabled = models.BooleanField(default=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    api_token = models.CharField(max_length=64, unique=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['greenhouse', 'code'], name='uq_device_greenhouse_code'),
        ]

    def save(self, *args, **kwargs):
        if not self.api_token:
            self.api_token = secrets.token_hex(24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.code})'


class DeviceState(TimeStampedModel):
    device = models.OneToOneField(Device, on_delete=models.CASCADE, related_name='state')
    is_on = models.BooleanField(default=False)
    desired_on = models.BooleanField(default=False)
    last_command = models.CharField(max_length=50, blank=True)
    last_value = models.CharField(max_length=50, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f'{self.device.code} state'


class SensorData(TimeStampedModel):
    greenhouse = models.ForeignKey(
        Greenhouse,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='sensor_readings',
        db_constraint=False,
    )
    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    humidity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    light = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    soil_moisture = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    received_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        indexes = [
            models.Index(fields=['recorded_at'], name='sensor_recorded_idx'),
        ]

    def __str__(self):
        return f'Reading #{self.pk} @ {self.recorded_at.isoformat()}'


class EstimationCycle(TimeStampedModel):
    class PreprocessStatus(models.TextChoices):
        VALID = 'valid', 'Valid'
        SKIPPED = 'skipped', 'Skipped'

    class CycleStatus(models.TextChoices):
        OK = 'ok', 'OK'
        SKIPPED_NO_MEASUREMENT = 'skipped_no_measurement', 'Skipped no measurement'
        ERROR = 'error', 'Error'

    class AdaptiveStatus(models.TextChoices):
        R_UPDATED = 'R_updated', 'R updated'
        R_SKIPPED = 'R_skipped', 'R skipped'
        SKIPPED = 'skipped', 'Skipped'

    sample_ts = models.DateTimeField(db_index=True)
    cycle_index = models.PositiveIntegerField(db_index=True)
    run = models.ForeignKey(
        ExperimentRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='estimation_cycles',
        db_constraint=False,
    )
    greenhouse = models.ForeignKey(
        Greenhouse,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='estimation_cycles',
        db_constraint=False,
    )
    slice_type = models.CharField(max_length=15, blank=True, default='online')
    source_type = models.CharField(max_length=20, blank=True, default='live')

    validation_status = models.CharField(max_length=32, blank=True)
    validation_reason = models.TextField(blank=True)
    preprocess_status = models.CharField(
        max_length=20,
        choices=PreprocessStatus.choices,
        default=PreprocessStatus.SKIPPED,
    )
    cycle_status = models.CharField(
        max_length=30,
        choices=CycleStatus.choices,
        default=CycleStatus.ERROR,
    )
    adaptive_status = models.CharField(
        max_length=20,
        choices=AdaptiveStatus.choices,
        default=AdaptiveStatus.SKIPPED,
    )

    raw_soil_moisture = models.FloatField(null=True, blank=True)
    raw_temperature = models.FloatField(null=True, blank=True)
    raw_humidity = models.FloatField(null=True, blank=True)
    raw_light = models.FloatField(null=True, blank=True)
    raw_drip = models.FloatField(null=True, blank=True)
    raw_mist = models.FloatField(null=True, blank=True)
    raw_fan = models.FloatField(null=True, blank=True)

    arx_predicted = models.FloatField(null=True, blank=True)
    kf_x_prior = models.FloatField(null=True, blank=True)
    kf_P_prior = models.FloatField(null=True, blank=True)
    kf_innovation = models.FloatField(null=True, blank=True)
    kf_R = models.FloatField(null=True, blank=True)
    kf_K = models.FloatField(null=True, blank=True)
    kf_x_posterior = models.FloatField(null=True, blank=True)
    kf_P_posterior = models.FloatField(null=True, blank=True)
    latency_ms = models.FloatField(null=True, blank=True)
    error_message = models.CharField(max_length=512, null=True, blank=True)
    ingest_dedupe_key = models.CharField(max_length=191, blank=True, default='')

    class Meta:
        ordering = ['-sample_ts', '-id']
        indexes = [
            models.Index(fields=['sample_ts', 'id'], name='est_sample_id_idx'),
            models.Index(fields=['cycle_status', 'sample_ts'], name='est_status_ts_idx'),
            models.Index(fields=['run', 'sample_ts'], name='est_run_ts_idx'),
            models.Index(fields=['greenhouse', 'sample_ts'], name='est_greenhouse_ts_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['run', 'cycle_index'],
                name='uq_api_est_run_cycle',
            ),
            models.UniqueConstraint(
                fields=['run', 'ingest_dedupe_key'],
                name='uq_api_est_run_dedupe',
            ),
        ]

    def __str__(self):
        return f'Estimation #{self.pk} @ {self.sample_ts.isoformat()}'


class ControlState(TimeStampedModel):
    class Mode(models.TextChoices):
        AUTO = 'AUTO', 'AUTO'
        MANUAL = 'MANUAL', 'MANUAL'

    singleton_key = models.CharField(max_length=20, unique=True, default='main')
    greenhouse = models.OneToOneField(
        Greenhouse,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='control_state',
        db_constraint=False,
    )
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.MANUAL)
    manual_reason = models.CharField(max_length=255, blank=True)
    manual_changed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Control state'
        verbose_name_plural = 'Control state'

    @classmethod
    def singleton_key_for_greenhouse(cls, greenhouse_id: int) -> str:
        max_length = cls._meta.get_field('singleton_key').max_length
        legacy_key = f'greenhouse:{greenhouse_id}'
        if len(legacy_key) <= max_length:
            return legacy_key
        return f'gh:{int(greenhouse_id):x}'

    def __str__(self):
        return f'Control<{self.mode}>'


class AMPCSchedulerState(TimeStampedModel):
    singleton_key = models.CharField(max_length=20, unique=True, default='main')
    greenhouse = models.ForeignKey(
        Greenhouse,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ampc_scheduler_states',
        db_constraint=False,
    )
    is_enabled = models.BooleanField(default=False)
    interval_seconds = models.PositiveIntegerField(default=300)
    is_executing = models.BooleanField(default=False)
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_stopped_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=40, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        verbose_name = 'AMPC scheduler state'
        verbose_name_plural = 'AMPC scheduler state'

    def __str__(self):
        status = 'enabled' if self.is_enabled else 'disabled'
        return f'AMPCScheduler<{status}>'


class ControlProfile(TimeStampedModel):
    singleton_key = models.CharField(max_length=20, unique=True, default='main')
    crop_name = models.CharField(max_length=100, default='Default crop')
    crop_kc = models.FloatField(default=1.0)

    target_low = models.FloatField(default=55.0)
    target_high = models.FloatField(default=65.0)
    step_seconds = models.PositiveIntegerField(default=300)
    horizon_steps = models.PositiveIntegerField(default=12)

    pump_min_seconds = models.FloatField(default=0.0)
    pump_max_seconds = models.FloatField(default=300.0)
    pump_grid_seconds = models.FloatField(default=30.0)
    soft_daily_pump_cap_seconds = models.FloatField(default=1800.0)

    weight_band = models.FloatField(default=10.0)
    weight_water = models.FloatField(default=0.2)
    weight_switch = models.FloatField(default=0.5)
    weight_daily = models.FloatField(default=2.0)
    weight_terminal = models.FloatField(default=20.0)

    adaptive_enabled = models.BooleanField(default=True)
    adaptive_bias_window = models.PositiveIntegerField(default=12)
    adaptive_max_abs_bias = models.FloatField(default=5.0)
    stale_after_seconds = models.PositiveIntegerField(default=600)

    actuator_enabled = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Control profile'
        verbose_name_plural = 'Control profile'

    def __str__(self):
        return f'ControlProfile<{self.crop_name}>'


class GreenhouseControlProfile(TimeStampedModel):
    greenhouse = models.OneToOneField(
        Greenhouse,
        on_delete=models.CASCADE,
        related_name='control_profile',
        db_constraint=False,
    )
    crop_name = models.CharField(max_length=100, default='Default crop')
    crop_kc = models.FloatField(default=1.0)
    latitude = models.FloatField(default=16.0471)
    longitude = models.FloatField(default=108.2068)
    soil_type = models.CharField(max_length=32, choices=FAO56_SOIL_TYPE_CHOICES, default='loam')
    theta_fc = models.FloatField(default=0.32)
    theta_wp = models.FloatField(default=0.15)
    theta_sat = models.FloatField(default=0.45)
    root_depth_m = models.FloatField(default=0.30)
    depletion_fraction_p = models.FloatField(default=0.5)
    pump_efficiency = models.FloatField(default=0.8)
    pump_flow_lps = models.FloatField(default=0.02)
    irrigation_area_m2 = models.FloatField(default=0.25)

    target_low = models.FloatField(default=55.0)
    target_high = models.FloatField(default=65.0)
    step_seconds = models.PositiveIntegerField(default=300)
    horizon_steps = models.PositiveIntegerField(default=12)

    pump_min_seconds = models.FloatField(default=0.0)
    pump_max_seconds = models.FloatField(default=300.0)
    pump_grid_seconds = models.FloatField(default=30.0)
    soft_daily_pump_cap_seconds = models.FloatField(default=1800.0)

    cost_band_violation = models.FloatField(default=10.0)
    cost_water_use = models.FloatField(default=0.2)
    cost_switching = models.FloatField(default=0.5)
    cost_daily_cap_excess = models.FloatField(default=2.0)
    cost_terminal_band_violation = models.FloatField(default=20.0)

    adaptive_enabled = models.BooleanField(default=True)
    adaptive_bias_window = models.PositiveIntegerField(default=12)
    adaptive_max_abs_bias = models.FloatField(default=5.0)
    safety_stale_after_seconds = models.PositiveIntegerField(default=600)

    actuator_enabled = models.BooleanField(default=False)
    actuator_url = models.CharField(max_length=500, blank=True, null=True)
    actuator_bearer_token_env = models.CharField(max_length=120, blank=True, null=True)
    actuator_timeout_seconds = models.FloatField(default=5.0)

    class Meta:
        db_table = 'greenhouse_control_profiles'
        ordering = ['greenhouse_id']

    @property
    def actuator_configured(self) -> bool:
        return bool(self.actuator_enabled and self.actuator_url)

    def __str__(self):
        return f'GreenhouseControlProfile<{self.greenhouse_id}:{self.crop_name}>'


class Alert(TimeStampedModel):
    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'
        SUCCESS = 'success', 'Success'

    level = models.CharField(max_length=20, choices=Level.choices, default=Level.WARNING)
    title = models.CharField(max_length=100)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    happened_at = models.DateTimeField(default=timezone.now, db_index=True)
    sensor_data = models.ForeignKey(
        SensorData,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='alerts',
    )
    device = models.ForeignKey(
        Device,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='alerts',
    )

    class Meta:
        ordering = ['-happened_at', '-id']

    def __str__(self):
        return f'[{self.level}] {self.title}'


class DeviceCommand(TimeStampedModel):
    class CommandStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACK = 'ack', 'Acknowledged'
        FAILED = 'failed', 'Failed'

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='commands')
    command = models.CharField(max_length=50)
    value = models.CharField(max_length=50, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=CommandStatus.choices,
        default=CommandStatus.PENDING,
    )
    acked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['status', '-created_at', '-id']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='cmd_status_created_idx'),
        ]

    def __str__(self):
        return f'{self.device.code}:{self.command}:{self.status}'


class AMPCRecommendation(TimeStampedModel):
    class ActuatorStatus(models.TextChoices):
        DISABLED = 'disabled', 'Disabled'
        NOT_CALLED = 'not_called', 'Not called'
        QUEUED = 'queued', 'Queued'
        DEVICE_NOT_FOUND = 'device_not_found', 'Device not found'
        UNSAFE_SKIPPED = 'unsafe_skipped', 'Unsafe skipped'

    sensor_data = models.ForeignKey(
        SensorData,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ampc_recommendations',
    )
    greenhouse = models.ForeignKey(
        Greenhouse,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ampc_recommendations',
        db_constraint=False,
    )
    run = models.ForeignKey(
        ExperimentRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ampc_recommendations',
        db_constraint=False,
    )
    estimation = models.ForeignKey(
        EstimationCycle,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ampc_recommendations',
    )
    device_command = models.ForeignKey(
        DeviceCommand,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ampc_recommendations',
    )

    mode = models.CharField(max_length=10, default=ControlState.Mode.MANUAL)
    pump_seconds = models.FloatField(default=0.0)
    step_seconds = models.PositiveIntegerField(default=300)
    predicted_soil_moisture = models.JSONField(default=list, blank=True)
    target_band = models.JSONField(default=dict, blank=True)
    objective_cost = models.FloatField(default=0.0)
    safety_status = models.CharField(max_length=40, default='pump_off_failsafe')
    reason = models.CharField(max_length=255, blank=True)
    bias_correction = models.FloatField(default=0.0)
    bias_window_count = models.PositiveIntegerField(default=0)
    used_today_pump_seconds = models.FloatField(default=0.0)
    command_created = models.BooleanField(default=False)
    actuator_status = models.CharField(
        max_length=30,
        choices=ActuatorStatus.choices,
        default=ActuatorStatus.NOT_CALLED,
    )
    config_snapshot = models.JSONField(default=dict, blank=True)
    state_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['created_at', 'safety_status'], name='ampc_created_safety_idx'),
        ]

    def __str__(self):
        return f'AMPCRecommendation<{self.safety_status}:{self.pump_seconds}>'
