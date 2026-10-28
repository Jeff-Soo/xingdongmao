# #057 P2-②：is_timed 收敛 —— 保存时一律 is_timed = (duration_seconds > 0)，
# 存量数据里两个字段可能各写各的（历史接口从请求里直接读 is_timed）。
# 这个迁移把存量对齐到唯一口径；数据本来就一致时一行都不改（幂等、可回退）。

from django.db import migrations


def align_is_timed(apps, schema_editor):
    QuickStep = apps.get_model('quick', 'QuickStep')
    turned_on = QuickStep.objects.filter(duration_seconds__gt=0, is_timed=False).update(is_timed=True)
    turned_off = QuickStep.objects.filter(duration_seconds=0, is_timed=True).update(is_timed=False)
    if turned_on or turned_off:
        print(f'\n  is_timed 对齐：置 True {turned_on} 行，置 False {turned_off} 行')


class Migration(migrations.Migration):

    dependencies = [
        ('quick', '0007_quickpattern_is_listed_quickpattern_is_verified'),
    ]

    operations = [
        migrations.RunPython(align_is_timed, migrations.RunPython.noop),
    ]
