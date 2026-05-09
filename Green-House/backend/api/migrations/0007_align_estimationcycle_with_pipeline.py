from django.db import connection, migrations, models


COPY_PIPELINE_SQL = """
UPDATE `api_ampcrecommendation`
SET `estimation_id` = NULL
WHERE `estimation_id` IS NOT NULL;

DELETE FROM `api_estimationcycle`;

INSERT INTO `api_estimationcycle` (
    `id`,
    `created_at`,
    `updated_at`,
    `sample_ts`,
    `cycle_index`,
    `run_id`,
    `greenhouse_id`,
    `slice_type`,
    `source_type`,
    `validation_status`,
    `validation_reason`,
    `preprocess_status`,
    `cycle_status`,
    `adaptive_status`,
    `raw_soil_moisture`,
    `raw_temperature`,
    `raw_humidity`,
    `raw_light`,
    `raw_drip`,
    `raw_mist`,
    `raw_fan`,
    `arx_predicted`,
    `kf_x_prior`,
    `kf_P_prior`,
    `kf_innovation`,
    `kf_R`,
    `kf_K`,
    `kf_x_posterior`,
    `kf_P_posterior`,
    `latency_ms`,
    `error_message`,
    `ingest_dedupe_key`
)
SELECT
    `id`,
    `created_at`,
    `created_at`,
    `sample_ts`,
    `cycle_index`,
    `run_id`,
    `greenhouse_id`,
    `slice_type`,
    `source_type`,
    '',
    '',
    `preprocess_status`,
    `cycle_status`,
    `adaptive_status`,
    `raw_soil_moisture`,
    `raw_temperature`,
    `raw_humidity`,
    `raw_light`,
    `raw_drip`,
    `raw_mist`,
    `raw_fan`,
    `arx_predicted`,
    `kf_x_prior`,
    `kf_P_prior`,
    `kf_innovation`,
    `kf_R`,
    `kf_K`,
    `kf_x_posterior`,
    `kf_P_posterior`,
    `latency_ms`,
    COALESCE(`error_message`, ''),
    `ingest_dedupe_key`
FROM `pipeline_cycles`;
"""


def copy_pipeline_cycles_if_present(apps, schema_editor):
    if 'pipeline_cycles' not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        cursor.execute(COPY_PIPELINE_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_controlprofile_alter_device_device_type_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='estimationcycle',
            old_name='temperature',
            new_name='raw_temperature',
        ),
        migrations.RenameField(
            model_name='estimationcycle',
            old_name='humidity',
            new_name='raw_humidity',
        ),
        migrations.RenameField(
            model_name='estimationcycle',
            old_name='light',
            new_name='raw_light',
        ),
        migrations.RenameField(
            model_name='estimationcycle',
            old_name='drip',
            new_name='raw_drip',
        ),
        migrations.RenameField(
            model_name='estimationcycle',
            old_name='mist',
            new_name='raw_mist',
        ),
        migrations.RenameField(
            model_name='estimationcycle',
            old_name='fan',
            new_name='raw_fan',
        ),
        migrations.AddField(
            model_name='estimationcycle',
            name='greenhouse_id',
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='estimationcycle',
            name='ingest_dedupe_key',
            field=models.CharField(blank=True, default='', max_length=191),
        ),
        migrations.AddField(
            model_name='estimationcycle',
            name='run_id',
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='estimationcycle',
            name='slice_type',
            field=models.CharField(blank=True, default='online', max_length=15),
        ),
        migrations.AddField(
            model_name='estimationcycle',
            name='source_type',
            field=models.CharField(blank=True, default='live', max_length=20),
        ),
        migrations.AlterField(
            model_name='estimationcycle',
            name='cycle_status',
            field=models.CharField(choices=[('ok', 'OK'), ('skipped_no_measurement', 'Skipped no measurement'), ('error', 'Error')], default='error', max_length=30),
        ),
        migrations.AlterField(
            model_name='estimationcycle',
            name='error_message',
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.RemoveField(
            model_name='estimationcycle',
            name='sensor_data',
        ),
        migrations.RunPython(copy_pipeline_cycles_if_present, reverse_code=migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='estimationcycle',
            constraint=models.UniqueConstraint(fields=('run_id', 'cycle_index'), name='uq_api_est_run_cycle'),
        ),
        migrations.AddConstraint(
            model_name='estimationcycle',
            constraint=models.UniqueConstraint(fields=('run_id', 'ingest_dedupe_key'), name='uq_api_est_run_dedupe'),
        ),
        migrations.AddIndex(
            model_name='estimationcycle',
            index=models.Index(fields=['run_id', 'sample_ts'], name='est_run_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='estimationcycle',
            index=models.Index(fields=['greenhouse_id', 'sample_ts'], name='est_greenhouse_ts_idx'),
        ),
    ]
