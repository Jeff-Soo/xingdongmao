# Generated manually for Phase 6 skip feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plans', '0007_userplanblock_floating_label_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userplanblock',
            name='is_skipped',
            field=models.BooleanField(default=False, help_text='今天不做了，归档到日历', verbose_name='已跳过'),
        ),
        migrations.AddField(
            model_name='dayexecution',
            name='skipped_blocks',
            field=models.PositiveIntegerField(default=0, verbose_name='跳过块数'),
        ),
    ]
