# Cleanup migration: add DayExecution mood/note, remove unused is_skipped

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plans', '0008_add_skip'),
    ]

    operations = [
        migrations.AddField(
            model_name='dayexecution',
            name='mood',
            field=models.CharField(blank=True, help_text='如 😊 😐 😢', max_length=50, verbose_name='当日感受'),
        ),
        migrations.AddField(
            model_name='dayexecution',
            name='note',
            field=models.TextField(blank=True, verbose_name='当日备注'),
        ),
        migrations.RemoveField(
            model_name='userplanblock',
            name='is_skipped',
        ),
    ]
