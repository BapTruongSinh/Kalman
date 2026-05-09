from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_green_house_server_cutover'),
    ]

    operations = [
        migrations.CreateModel(
            name='AMPCSchedulerState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('singleton_key', models.CharField(default='main', max_length=20, unique=True)),
                ('is_enabled', models.BooleanField(default=False)),
                ('interval_seconds', models.PositiveIntegerField(default=300)),
                ('is_executing', models.BooleanField(default=False)),
                ('last_started_at', models.DateTimeField(blank=True, null=True)),
                ('last_stopped_at', models.DateTimeField(blank=True, null=True)),
                ('last_run_at', models.DateTimeField(blank=True, null=True)),
                ('next_run_at', models.DateTimeField(blank=True, null=True)),
                ('last_status', models.CharField(blank=True, max_length=40)),
                ('last_error', models.TextField(blank=True)),
                ('greenhouse', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ampc_scheduler_states', to='api.greenhouse')),
            ],
            options={
                'verbose_name': 'AMPC scheduler state',
                'verbose_name_plural': 'AMPC scheduler state',
            },
        ),
    ]
