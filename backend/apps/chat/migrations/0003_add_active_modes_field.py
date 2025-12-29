# Generated manually for chat modes feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='active_modes',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
