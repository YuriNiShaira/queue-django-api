from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('queueing', '0009_delete_activesession'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='auto_cutoff_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='service',
            name='auto_schedule_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='service',
            name='auto_start_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]