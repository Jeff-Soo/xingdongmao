from django.db import models, transaction
from django.conf import settings


class UserPlan(models.Model):
    """个人计划（用户 Fork 模板后生成的副本）"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='plans')
    pattern = models.ForeignKey('patterns.Pattern', on_delete=models.SET_NULL, null=True, blank=True, related_name='forks')
    title = models.CharField('计划标题', max_length=200)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    is_enabled = models.BooleanField('是否启用', default=True,
        help_text='用户可在计划列表页勾选/取消启用的 Plan，执行页只展示已启用的 Plan')
    is_public = models.BooleanField('是否公开', default=False,
        help_text='用户手动发布后置为 True，公开计划可被搜索和 Fork')
    activated_date = models.DateField('激活日期', null=True, blank=True)
    mood = models.CharField('感受', max_length=50, blank=True, help_text='如 😊 😐 😢')
    note = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '个人计划'
        verbose_name_plural = '个人计划'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    @property
    def is_all_completed(self):
        blocks = self.blocks.all()
        return blocks.exists() and all(b.is_completed for b in blocks)

    @classmethod
    @transaction.atomic
    def fork_from_pattern(cls, pattern, user):
        """从 Pattern 克隆一份 UserPlan + UserPlanBlock"""
        # 1. 创建 UserPlan
        plan = cls.objects.create(
            user=user,
            pattern=pattern,
            title=pattern.title,
        )
        # 2. 遍历 TimeBlock，逐个克隆
        for tb in pattern.time_blocks.all():
            UserPlanBlock.objects.create(
                plan=plan,
                source_block=tb,
                order=tb.order,
                start_time=tb.start_time or '00:00',
                end_time=tb.end_time or '00:00',
                action=tb.action,
                notes=tb.notes,
                alt_action=tb.alt_action,
                alt_duration_minutes=tb.alt_duration_minutes,
                is_floating=tb.is_floating,
                floating_label=tb.floating_label,
            )
        return plan


class UserPlanBlock(models.Model):
    """个人计划的时间块"""
    plan = models.ForeignKey(UserPlan, on_delete=models.CASCADE, related_name='blocks')
    source_block = models.ForeignKey('patterns.TimeBlock', on_delete=models.SET_NULL, null=True, blank=True)
    order = models.PositiveIntegerField('顺序', default=0)
    start_time = models.TimeField('开始时间')
    end_time = models.TimeField('结束时间')
    action = models.CharField('动作', max_length=255)
    notes = models.TextField('备注', blank=True)
    is_completed = models.BooleanField('是否完成', default=False)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    is_skipped = models.BooleanField('已跳过', default=False, help_text='今天不做了，归档到日历')
    original_action = models.CharField('原始动作', max_length=255, blank=True)
    original_end_time = models.TimeField('原始结束时间', null=True, blank=True)
    alt_action = models.CharField('备选动作', max_length=255, blank=True)
    alt_duration_minutes = models.PositiveIntegerField('缩短时长（分钟）', null=True, blank=True)
    is_floating = models.BooleanField('浮动时间', default=False)
    floating_label = models.CharField('浮动标签', max_length=50, blank=True)
    has_time_conflict = models.BooleanField('时间冲突', default=False)
    conflict_note = models.CharField('冲突说明', max_length=255, blank=True,help_text='记得把时间改好，否则会冲突哦！')


    class Meta:
        verbose_name = '时间块'
        verbose_name_plural = '时间块'
        ordering = ['start_time']

    def __str__(self):
        return f'{self.start_time}-{self.end_time} {self.action}'

class DayExecution(models.Model):
    """每日执行快照——记录某一天用户所有已启用 Plan 的汇总完成情况"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField('执行日期')
    total_blocks = models.PositiveIntegerField('总块数')
    completed_blocks = models.PositiveIntegerField('完成块数')
    skipped_blocks = models.PositiveIntegerField('跳过块数', default=0)
    completion_rate = models.FloatField('完成率', default=0)  # 0.0 ~ 1.0
    mood = models.CharField('当日感受', max_length=50, blank=True, help_text='如 😊 😐 😢')
    note = models.TextField('当日备注', blank=True)
    enabled_plans = models.ManyToManyField(UserPlan, blank=True, verbose_name='当天启用的计划')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '每日执行'
        verbose_name_plural = '每日执行'
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='unique_user_date')
        ]

    def __str__(self):
        return f'{self.date} 完成率 {self.completion_rate:.0%}'