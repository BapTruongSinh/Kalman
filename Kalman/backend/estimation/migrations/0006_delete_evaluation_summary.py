from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("estimation", "0005_pipelinecycle_ingest_dedupe_key"),
    ]

    operations = [
        migrations.DeleteModel(
            name="EvaluationSummary",
        ),
    ]
