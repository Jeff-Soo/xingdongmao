"""#087：把老的 UserTaskStep.is_done 迁移成「今天」的 TaskDay 记录。

为什么这么迁：老的 is_done 只有布尔，没有"哪天勾的"。Jeff 给了两个选项
（当成"最近一次完成" / 直接清空）。测试期数据量小，这里选"当成最近一次 = 今天"，
这样已经勾过的任务不会凭空丢进度。

迁移之后 is_done 仍保留，但语义变成"今天这一步勾没勾"的缓存（打勾时同步写），
所有读接口都改成按 TaskDay 判断。
"""

from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    TaskDay = apps.get_model('tasks', 'TaskDay')
    UserTask = apps.get_model('tasks', 'UserTask')

    today = timezone.localtime(timezone.now()).date()
    for task in UserTask.objects.all().iterator():
        done_ids = list(task.steps.filter(is_done=True).values_list('id', flat=True))
        if not done_ids:
            continue
        total = task.steps.count()
        TaskDay.objects.update_or_create(
            task_id=task.pk,
            date=today,
            defaults={
                'user_id': task.user_id,
                'done_step_ids': done_ids,
                'done_count': len(done_ids),
                'completed': total > 0 and len(done_ids) >= total,
            },
        )


def backwards(apps, schema_editor):
    TaskDay = apps.get_model('tasks', 'TaskDay')
    UserTask = apps.get_model('tasks', 'UserTask')

    today = timezone.localtime(timezone.now()).date()
    for day in TaskDay.objects.filter(date=today).iterator():
        task = UserTask.objects.filter(pk=day.task_id).first()
        if not task:
            continue
        task.steps.all().update(is_done=False)
        task.steps.filter(id__in=day.done_step_ids).update(is_done=True)


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0004_taskday'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
