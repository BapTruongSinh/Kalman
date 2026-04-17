# Generated manually for MySQL-compatible uniqueness (replaces partial unique).

from django.db import migrations, models
from django.db.models import Count, Max

# Same channel order as live ingestion ``raw_*`` columns (for duplicate resolution).
_RAW_SENSOR_FIELDS = (
    "raw_soil_moisture",
    "raw_temperature",
    "raw_humidity",
    "raw_light",
    "raw_drip",
    "raw_mist",
    "raw_fan",
)


def _raw_sensor_tuple(cycle) -> tuple:
    return tuple(getattr(cycle, f) for f in _RAW_SENSOR_FIELDS)


def _backfill_ingest_dedupe_key(apps, schema_editor):
    PipelineCycle = apps.get_model("estimation", "PipelineCycle")
    from datetime import timezone

    rows = []
    for c in PipelineCycle.objects.all().only(
        "id",
        "run_id",
        "source_type",
        "sample_ts",
        "cycle_index",
    ).iterator():
        if c.source_type == "live":
            ts = c.sample_ts
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            key = f"live|{c.run_id}|{ts.isoformat()}"
        elif c.source_type == "csv_replay":
            key = f"csv|{c.run_id}|{c.cycle_index:010d}"
        elif c.source_type == "mysql_replay":
            key = f"mysql|{c.run_id}|{c.cycle_index:010d}"
        else:
            raise ValueError(f"unknown source_type {c.source_type!r} for cycle {c.pk}")
        c.ingest_dedupe_key = key
        rows.append(c)
        if len(rows) >= 500:
            PipelineCycle.objects.bulk_update(rows, ["ingest_dedupe_key"])
            rows = []
    if rows:
        PipelineCycle.objects.bulk_update(rows, ["ingest_dedupe_key"])


def _resolve_duplicate_ingest_keys_before_unique(apps, schema_editor):
    """Drop redundant rows that share (run, ingest_dedupe_key) before UNIQUE is added.

    Older deployments could insert multiple **live** rows for the same
    ``run_id`` + ``sample_ts`` when the partial unique index was a no-op on
    MySQL. After backfill they collide on ``ingest_dedupe_key``.

    Kalman is stateful: removing a duplicate that was *not* at the tail of the
    run would leave later ``kf_*`` rows computed from the wrong state. We
    therefore only auto-delete when the duplicate group is at the **end** of
    the run (no row in that run has a higher ``cycle_index`` than the group's
    maximum).

    * Identical raw payloads **and** tail-only → keep lowest ``id``, delete rest.
    * Identical raw payloads but later cycles exist → ``ValueError`` (replay /
      rebuild / trim later rows).
    * Conflicting raw payloads → ``ValueError`` with cycle IDs (manual fix).
    """
    PipelineCycle = apps.get_model("estimation", "PipelineCycle")

    dup_groups = (
        PipelineCycle.objects.values("run_id", "ingest_dedupe_key")
        .annotate(n=Count("pk"))
        .filter(n__gt=1)
    )

    for g in dup_groups:
        run_id = g["run_id"]
        key = g["ingest_dedupe_key"]
        rows = list(
            PipelineCycle.objects.filter(run_id=run_id, ingest_dedupe_key=key).order_by(
                "id"
            )
        )
        if len(rows) < 2:
            continue

        ids = [r.pk for r in rows]
        max_idx_in_group = max(r.cycle_index for r in rows)
        run_max_idx = (
            PipelineCycle.objects.filter(run_id=run_id).aggregate(m=Max("cycle_index")).get("m")
        )
        if run_max_idx is None:
            run_max_idx = max_idx_in_group

        ref = _raw_sensor_tuple(rows[0])
        same_payload = all(_raw_sensor_tuple(r) == ref for r in rows[1:])

        if not same_payload:
            raise ValueError(
                "estimation migration 0005: duplicate (run_id, ingest_dedupe_key) "
                f"with conflicting raw sensor payloads — ingest_dedupe_key={key!r}, "
                f"run_id={run_id}, pipeline_cycles.id in {ids}. "
                "Delete or correct these rows manually, then run migrate again."
            )

        if run_max_idx > max_idx_in_group:
            raise ValueError(
                "estimation migration 0005: duplicate (run_id, ingest_dedupe_key) with "
                "identical raw payloads, but this run has later cycles whose Kalman "
                f"state may depend on the extra duplicate rows. run_id={run_id}, "
                f"ingest_dedupe_key={key!r}, max cycle_index in duplicate group={max_idx_in_group}, "
                f"max cycle_index in run={run_max_idx}, pipeline_cycles.id in {ids}. "
                "Replay/recompute the run from a clean snapshot, or remove later cycles, "
                "then run migrate again."
            )

        delete_ids = [r.pk for r in rows[1:]]
        PipelineCycle.objects.filter(pk__in=delete_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("estimation", "0004_experiment_run_owner_live_sample_ts_unique"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="pipelinecycle",
            name="uq_cycles_run_live_sample_ts",
        ),
        migrations.AddField(
            model_name="pipelinecycle",
            name="ingest_dedupe_key",
            field=models.CharField(
                help_text=(
                    "Stable key for DB uniqueness: live=run+UTC timestamp; "
                    "replay=run+cycle_index (allows duplicate sample_ts in CSV)."
                ),
                max_length=191,
                null=True,
            ),
        ),
        migrations.RunPython(_backfill_ingest_dedupe_key, migrations.RunPython.noop),
        migrations.RunPython(
            _resolve_duplicate_ingest_keys_before_unique,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="pipelinecycle",
            name="ingest_dedupe_key",
            field=models.CharField(
                help_text=(
                    "Stable key for DB uniqueness: live=run+UTC timestamp; "
                    "replay=run+cycle_index (allows duplicate sample_ts in CSV)."
                ),
                max_length=191,
            ),
        ),
        migrations.AddConstraint(
            model_name="pipelinecycle",
            constraint=models.UniqueConstraint(
                fields=("run", "ingest_dedupe_key"),
                name="uq_cycles_run_ingest_dedupe",
            ),
        ),
    ]
