# Generated manually for task #008 — evaluation metrics and report export

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estimation', '0002_pipeline_cycle_adaptive_status_check_constraints'),
    ]

    operations = [
        # ── PipelineCycle: add latency_ms ─────────────────────────────────────
        migrations.AddField(
            model_name='pipelinecycle',
            name='latency_ms',
            field=models.FloatField(
                blank=True,
                null=True,
                help_text='Wall-clock time for this Kalman step in milliseconds',
            ),
        ),

        # ── EvaluationSummary: adaptive status distribution ───────────────────
        migrations.AddField(
            model_name='evaluationsummary',
            name='n_r_updated',
            field=models.IntegerField(
                default=0,
                help_text='Cycles where adaptive R was updated (R_updated)',
            ),
        ),
        migrations.AddField(
            model_name='evaluationsummary',
            name='n_r_skipped',
            field=models.IntegerField(
                default=0,
                help_text='Cycles where R update was skipped (no measurement)',
            ),
        ),
        migrations.AddField(
            model_name='evaluationsummary',
            name='n_adaptive_skipped',
            field=models.IntegerField(
                default=0,
                help_text='Cycles on the error path (adaptive_status=skipped)',
            ),
        ),

        # ── EvaluationSummary: latency stats ──────────────────────────────────
        migrations.AddField(
            model_name='evaluationsummary',
            name='latency_mean_ms',
            field=models.FloatField(
                blank=True,
                null=True,
                help_text='Mean wall-clock time per Kalman step in milliseconds',
            ),
        ),
        migrations.AddField(
            model_name='evaluationsummary',
            name='latency_p95_ms',
            field=models.FloatField(
                blank=True,
                null=True,
                help_text='95th-percentile wall-clock time per step in milliseconds',
            ),
        ),
    ]
