# Generated manually for the Green-House server cutover.

from django.conf import settings
from django.db import connection, migrations, models
import django.db.models.deletion
import django.utils.timezone


CREATE_DOMAIN_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS `greenhouses` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `name` varchar(120) NOT NULL,
  `location` varchar(255) NULL,
  `is_active` bool NOT NULL DEFAULT 1,
  `notes` longtext NULL,
  `owner_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_greenhouse_owner_name` (`owner_id`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `experiment_runs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `name` varchar(120) NOT NULL,
  `run_type` varchar(20) NOT NULL DEFAULT 'live',
  `status` varchar(20) NOT NULL DEFAULT 'running',
  `dataset_source` varchar(255) NOT NULL DEFAULT '',
  `started_at` datetime(6) NOT NULL,
  `completed_at` datetime(6) NULL,
  `notes` longtext NOT NULL,
  `greenhouse_id` bigint NULL,
  PRIMARY KEY (`id`),
  KEY `experiment_runs_greenhouse_id_idx` (`greenhouse_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `experiment_configs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `x0` double NOT NULL DEFAULT 0,
  `P0` double NOT NULL DEFAULT 1,
  `Q` double NOT NULL DEFAULT 0.01,
  `R0` double NOT NULL DEFAULT 1,
  `R_min` double NOT NULL DEFAULT 0.01,
  `R_max` double NOT NULL DEFAULT 25,
  `alpha` double NOT NULL DEFAULT 0.05,
  `raw_config_json` json NOT NULL,
  `run_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `experiment_configs_run_id_uniq` (`run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `evaluation_summaries` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `total_samples` int unsigned NOT NULL DEFAULT 0,
  `accepted_samples` int unsigned NOT NULL DEFAULT 0,
  `dropped_samples` int unsigned NOT NULL DEFAULT 0,
  `success_cycles` int unsigned NOT NULL DEFAULT 0,
  `failed_cycles` int unsigned NOT NULL DEFAULT 0,
  `mae_arx_vs_observed` double NULL,
  `mae_kf_vs_observed` double NULL,
  `rmse_arx_vs_observed` double NULL,
  `rmse_kf_vs_observed` double NULL,
  `avg_latency_ms` double NULL,
  `p95_latency_ms` double NULL,
  `max_latency_ms` double NULL,
  `avg_R` double NULL,
  `min_R` double NULL,
  `max_R` double NULL,
  `acceptance_gate_json` json NOT NULL,
  `run_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `evaluation_summaries_run_id_uniq` (`run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `greenhouse_control_profiles` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `crop_name` varchar(100) NOT NULL DEFAULT 'Default crop',
  `crop_kc` double NOT NULL DEFAULT 1,
  `target_low` double NOT NULL DEFAULT 55,
  `target_high` double NOT NULL DEFAULT 65,
  `step_seconds` int unsigned NOT NULL DEFAULT 300,
  `horizon_steps` int unsigned NOT NULL DEFAULT 12,
  `pump_min_seconds` double NOT NULL DEFAULT 0,
  `pump_max_seconds` double NOT NULL DEFAULT 300,
  `pump_grid_seconds` double NOT NULL DEFAULT 30,
  `soft_daily_pump_cap_seconds` double NOT NULL DEFAULT 1800,
  `cost_band_violation` double NOT NULL DEFAULT 10,
  `cost_water_use` double NOT NULL DEFAULT 0.2,
  `cost_switching` double NOT NULL DEFAULT 0.5,
  `cost_daily_cap_excess` double NOT NULL DEFAULT 2,
  `cost_terminal_band_violation` double NOT NULL DEFAULT 20,
  `adaptive_enabled` bool NOT NULL DEFAULT 1,
  `adaptive_bias_window` int unsigned NOT NULL DEFAULT 12,
  `adaptive_max_abs_bias` double NOT NULL DEFAULT 5,
  `safety_stale_after_seconds` int unsigned NOT NULL DEFAULT 600,
  `actuator_enabled` bool NOT NULL DEFAULT 0,
  `actuator_url` varchar(500) NULL,
  `actuator_bearer_token_env` varchar(120) NULL,
  `actuator_timeout_seconds` double NOT NULL DEFAULT 5,
  `greenhouse_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `greenhouse_control_profiles_greenhouse_id_uniq` (`greenhouse_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


DROP_LEGACY_PIPELINE_SQL = """
DROP TABLE IF EXISTS `ampc_recommendations`;
DROP TABLE IF EXISTS `pipeline_cycles`;
"""


def _table_columns(table_name: str) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(f'SHOW COLUMNS FROM `{table_name}`')
        return {row[0] for row in cursor.fetchall()}


def _add_column_if_missing(table_name: str, column_name: str, definition: str) -> None:
    if column_name in _table_columns(table_name):
        return
    with connection.cursor() as cursor:
        cursor.execute(f'ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {definition}')


def ensure_cutover_columns(apps, schema_editor):
    existing_tables = set(connection.introspection.table_names())

    if 'experiment_runs' in existing_tables:
        _add_column_if_missing('experiment_runs', 'updated_at', 'datetime(6) NULL')
        _add_column_if_missing('experiment_runs', 'greenhouse_id', 'bigint NULL')

    if 'experiment_configs' in existing_tables:
        _add_column_if_missing('experiment_configs', 'updated_at', 'datetime(6) NULL')

    if 'evaluation_summaries' in existing_tables:
        for column_name, definition in {
            'updated_at': 'datetime(6) NULL',
            'total_samples': 'int unsigned NOT NULL DEFAULT 0',
            'accepted_samples': 'int unsigned NOT NULL DEFAULT 0',
            'dropped_samples': 'int unsigned NOT NULL DEFAULT 0',
            'success_cycles': 'int unsigned NOT NULL DEFAULT 0',
            'failed_cycles': 'int unsigned NOT NULL DEFAULT 0',
            'mae_arx_vs_observed': 'double NULL',
            'mae_kf_vs_observed': 'double NULL',
            'rmse_arx_vs_observed': 'double NULL',
            'rmse_kf_vs_observed': 'double NULL',
            'avg_latency_ms': 'double NULL',
            'p95_latency_ms': 'double NULL',
            'max_latency_ms': 'double NULL',
            'avg_R': 'double NULL',
            'min_R': 'double NULL',
            'max_R': 'double NULL',
            'acceptance_gate_json': 'json NULL',
        }.items():
            _add_column_if_missing('evaluation_summaries', column_name, definition)

    for table_name in ('api_ampcrecommendation', 'api_device', 'api_sensordata', 'api_controlstate'):
        if table_name in existing_tables:
            _add_column_if_missing(table_name, 'greenhouse_id', 'bigint NULL')
    if 'api_ampcrecommendation' in existing_tables:
        _add_column_if_missing('api_ampcrecommendation', 'run_id', 'bigint NULL')


def seed_cutover_defaults(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Greenhouse = apps.get_model('api', 'Greenhouse')
    ExperimentRun = apps.get_model('api', 'ExperimentRun')
    SensorData = apps.get_model('api', 'SensorData')
    EstimationCycle = apps.get_model('api', 'EstimationCycle')
    ControlProfile = apps.get_model('api', 'ControlProfile')
    GreenhouseControlProfile = apps.get_model('api', 'GreenhouseControlProfile')
    ControlState = apps.get_model('api', 'ControlState')
    Device = apps.get_model('api', 'Device')
    AMPCRecommendation = apps.get_model('api', 'AMPCRecommendation')

    owner = User.objects.order_by('id').first()
    if owner is None:
        owner = User.objects.create_user(username='local_admin')

    greenhouse = Greenhouse.objects.order_by('id').first()
    if greenhouse is None:
        greenhouse = Greenhouse.objects.create(owner=owner, name='Main greenhouse', is_active=True)

    run = ExperimentRun.objects.order_by('id').first()
    if run is None:
        run = ExperimentRun.objects.create(
            name='Live run',
            run_type='live',
            status='running',
            dataset_source='green_house',
            greenhouse=greenhouse,
        )
    elif run.greenhouse_id is None:
        run.greenhouse = greenhouse
        run.save(update_fields=['greenhouse', 'updated_at'])

    SensorData.objects.filter(greenhouse__isnull=True).update(greenhouse=greenhouse)
    EstimationCycle.objects.filter(greenhouse__isnull=True).update(greenhouse=greenhouse)
    EstimationCycle.objects.filter(run__isnull=True).update(run=run)
    ControlState.objects.filter(greenhouse__isnull=True).update(greenhouse=greenhouse)
    Device.objects.filter(greenhouse__isnull=True).update(greenhouse=greenhouse)
    AMPCRecommendation.objects.filter(greenhouse__isnull=True).update(greenhouse=greenhouse)
    AMPCRecommendation.objects.filter(run__isnull=True).update(run=run)

    legacy = ControlProfile.objects.order_by('id').first()
    if legacy is not None:
        GreenhouseControlProfile.objects.get_or_create(
            greenhouse=greenhouse,
            defaults={
                'crop_name': legacy.crop_name,
                'crop_kc': legacy.crop_kc,
                'target_low': legacy.target_low,
                'target_high': legacy.target_high,
                'step_seconds': legacy.step_seconds,
                'horizon_steps': legacy.horizon_steps,
                'pump_min_seconds': legacy.pump_min_seconds,
                'pump_max_seconds': legacy.pump_max_seconds,
                'pump_grid_seconds': legacy.pump_grid_seconds,
                'soft_daily_pump_cap_seconds': legacy.soft_daily_pump_cap_seconds,
                'cost_band_violation': legacy.weight_band,
                'cost_water_use': legacy.weight_water,
                'cost_switching': legacy.weight_switch,
                'cost_daily_cap_excess': legacy.weight_daily,
                'cost_terminal_band_violation': legacy.weight_terminal,
                'adaptive_enabled': legacy.adaptive_enabled,
                'adaptive_bias_window': legacy.adaptive_bias_window,
                'adaptive_max_abs_bias': legacy.adaptive_max_abs_bias,
                'safety_stale_after_seconds': legacy.stale_after_seconds,
                'actuator_enabled': legacy.actuator_enabled,
            },
        )


def verify_cycles_before_drop(apps, schema_editor):
    tables = set(connection.introspection.table_names())
    if 'pipeline_cycles' not in tables:
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM `pipeline_cycles`')
        pipeline_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM `api_estimationcycle`')
        api_count = cursor.fetchone()[0]
    if pipeline_count and api_count < pipeline_count:
        raise RuntimeError(
            f'api_estimationcycle has {api_count} rows, less than pipeline_cycles {pipeline_count}; refusing to drop legacy table'
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0007_align_estimationcycle_with_pipeline'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(CREATE_DOMAIN_TABLES_SQL, reverse_sql=migrations.RunSQL.noop),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='Greenhouse',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('name', models.CharField(max_length=120)),
                        ('location', models.CharField(blank=True, max_length=255, null=True)),
                        ('is_active', models.BooleanField(default=True)),
                        ('notes', models.TextField(blank=True, null=True)),
                        ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='greenhouses', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={'db_table': 'greenhouses', 'ordering': ['id']},
                ),
                migrations.CreateModel(
                    name='ExperimentRun',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('name', models.CharField(max_length=120)),
                        ('run_type', models.CharField(choices=[('live', 'Live')], default='live', max_length=20)),
                        ('status', models.CharField(choices=[('created', 'Created'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed')], default='running', max_length=20)),
                        ('dataset_source', models.CharField(blank=True, max_length=255)),
                        ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                        ('completed_at', models.DateTimeField(blank=True, null=True)),
                        ('notes', models.TextField(blank=True)),
                        ('greenhouse', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='runs', to='api.greenhouse')),
                    ],
                    options={'db_table': 'experiment_runs', 'ordering': ['-created_at', '-id']},
                ),
                migrations.CreateModel(
                    name='ExperimentConfig',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('x0', models.FloatField(default=0.0)),
                        ('P0', models.FloatField(default=1.0)),
                        ('Q', models.FloatField(default=0.01)),
                        ('R0', models.FloatField(default=1.0)),
                        ('R_min', models.FloatField(default=0.01)),
                        ('R_max', models.FloatField(default=25.0)),
                        ('alpha', models.FloatField(default=0.05)),
                        ('raw_config_json', models.JSONField(blank=True, default=dict)),
                        ('run', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='config', to='api.experimentrun')),
                    ],
                    options={'db_table': 'experiment_configs'},
                ),
                migrations.CreateModel(
                    name='EvaluationSummary',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('total_samples', models.PositiveIntegerField(default=0)),
                        ('accepted_samples', models.PositiveIntegerField(default=0)),
                        ('dropped_samples', models.PositiveIntegerField(default=0)),
                        ('success_cycles', models.PositiveIntegerField(default=0)),
                        ('failed_cycles', models.PositiveIntegerField(default=0)),
                        ('mae_arx_vs_observed', models.FloatField(blank=True, null=True)),
                        ('mae_kf_vs_observed', models.FloatField(blank=True, null=True)),
                        ('rmse_arx_vs_observed', models.FloatField(blank=True, null=True)),
                        ('rmse_kf_vs_observed', models.FloatField(blank=True, null=True)),
                        ('avg_latency_ms', models.FloatField(blank=True, null=True)),
                        ('p95_latency_ms', models.FloatField(blank=True, null=True)),
                        ('max_latency_ms', models.FloatField(blank=True, null=True)),
                        ('avg_R', models.FloatField(blank=True, null=True)),
                        ('min_R', models.FloatField(blank=True, null=True)),
                        ('max_R', models.FloatField(blank=True, null=True)),
                        ('acceptance_gate_json', models.JSONField(blank=True, default=dict)),
                        ('run', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='evaluation_summary', to='api.experimentrun')),
                    ],
                    options={'db_table': 'evaluation_summaries'},
                ),
                migrations.CreateModel(
                    name='GreenhouseControlProfile',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('crop_name', models.CharField(default='Default crop', max_length=100)),
                        ('crop_kc', models.FloatField(default=1.0)),
                        ('target_low', models.FloatField(default=55.0)),
                        ('target_high', models.FloatField(default=65.0)),
                        ('step_seconds', models.PositiveIntegerField(default=300)),
                        ('horizon_steps', models.PositiveIntegerField(default=12)),
                        ('pump_min_seconds', models.FloatField(default=0.0)),
                        ('pump_max_seconds', models.FloatField(default=300.0)),
                        ('pump_grid_seconds', models.FloatField(default=30.0)),
                        ('soft_daily_pump_cap_seconds', models.FloatField(default=1800.0)),
                        ('cost_band_violation', models.FloatField(default=10.0)),
                        ('cost_water_use', models.FloatField(default=0.2)),
                        ('cost_switching', models.FloatField(default=0.5)),
                        ('cost_daily_cap_excess', models.FloatField(default=2.0)),
                        ('cost_terminal_band_violation', models.FloatField(default=20.0)),
                        ('adaptive_enabled', models.BooleanField(default=True)),
                        ('adaptive_bias_window', models.PositiveIntegerField(default=12)),
                        ('adaptive_max_abs_bias', models.FloatField(default=5.0)),
                        ('safety_stale_after_seconds', models.PositiveIntegerField(default=600)),
                        ('actuator_enabled', models.BooleanField(default=False)),
                        ('actuator_url', models.CharField(blank=True, max_length=500, null=True)),
                        ('actuator_bearer_token_env', models.CharField(blank=True, max_length=120, null=True)),
                        ('actuator_timeout_seconds', models.FloatField(default=5.0)),
                        ('greenhouse', models.OneToOneField(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='control_profile', to='api.greenhouse')),
                    ],
                    options={'db_table': 'greenhouse_control_profiles', 'ordering': ['greenhouse_id']},
                ),
                migrations.AddConstraint(
                    model_name='greenhouse',
                    constraint=models.UniqueConstraint(fields=('owner', 'name'), name='uq_greenhouse_owner_name'),
                ),
            ],
        ),
        migrations.RunPython(ensure_cutover_columns, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='ampcrecommendation',
                    name='greenhouse',
                    field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ampc_recommendations', to='api.greenhouse'),
                ),
                migrations.AddField(
                    model_name='ampcrecommendation',
                    name='run',
                    field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ampc_recommendations', to='api.experimentrun'),
                ),
                migrations.AddField(
                    model_name='controlstate',
                    name='greenhouse',
                    field=models.OneToOneField(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='control_state', to='api.greenhouse'),
                ),
                migrations.AddField(
                    model_name='device',
                    name='greenhouse',
                    field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='devices', to='api.greenhouse'),
                ),
                migrations.AddField(
                    model_name='sensordata',
                    name='greenhouse',
                    field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sensor_readings', to='api.greenhouse'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveConstraint(model_name='estimationcycle', name='uq_api_est_run_cycle'),
                migrations.RemoveConstraint(model_name='estimationcycle', name='uq_api_est_run_dedupe'),
                migrations.RemoveIndex(model_name='estimationcycle', name='est_run_ts_idx'),
                migrations.RemoveIndex(model_name='estimationcycle', name='est_greenhouse_ts_idx'),
                migrations.RemoveField(model_name='estimationcycle', name='greenhouse_id'),
                migrations.RemoveField(model_name='estimationcycle', name='run_id'),
                migrations.AddField(
                    model_name='estimationcycle',
                    name='greenhouse',
                    field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='estimation_cycles', to='api.greenhouse'),
                ),
                migrations.AddField(
                    model_name='estimationcycle',
                    name='run',
                    field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='estimation_cycles', to='api.experimentrun'),
                ),
                migrations.AddIndex(
                    model_name='estimationcycle',
                    index=models.Index(fields=['run', 'sample_ts'], name='est_run_ts_idx'),
                ),
                migrations.AddIndex(
                    model_name='estimationcycle',
                    index=models.Index(fields=['greenhouse', 'sample_ts'], name='est_greenhouse_ts_idx'),
                ),
                migrations.AddConstraint(
                    model_name='estimationcycle',
                    constraint=models.UniqueConstraint(fields=('run', 'cycle_index'), name='uq_api_est_run_cycle'),
                ),
                migrations.AddConstraint(
                    model_name='estimationcycle',
                    constraint=models.UniqueConstraint(fields=('run', 'ingest_dedupe_key'), name='uq_api_est_run_dedupe'),
                ),
            ],
        ),
        migrations.RunPython(seed_cutover_defaults, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(verify_cycles_before_drop, reverse_code=migrations.RunPython.noop),
        migrations.RunSQL(DROP_LEGACY_PIPELINE_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
