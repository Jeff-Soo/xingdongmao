"""日常任务层（#079）：把「模板」变成「每天要做的事」，并记录每一步的落勾。

为什么单独建表，而不是复用 plans.UserPlan：
- UserPlan 是「钟点时间块」（start_time~end_time + 冲突检测 + 浮动块），那条产品线已经下线；
- 现在要的是「任务清单 + 步骤打勾 + 进度」，两者结构不一样，硬套会让用户填一堆开始/结束时间；
- AGENTS.md §3（2026-10 修订）：不合并表，靠 FK 打通 —— 这里用 source_pattern 指向 quick 模板。

快照策略：建任务时把 QuickStep 复制成 UserTaskStep。
模板后来改了/删了都不影响已经建好的任务（source_pattern 用 SET_NULL：只断来源，不删任务）。
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# t-box 时间段：spec 允许自定义（如"通勤时"），所以 timeslot 用 CharField 而不是 choices。
# 这两个表只给「排序 / 展示」用，取值不在表里的自定义时间段排在最后。
TIMESLOT_ORDER = {
    'morning': 10,
    'noon': 20,
    'afternoon': 30,
    'evening': 40,
    'night': 50,
}
TIMESLOT_LABELS = {
    'morning': '早上',
    'noon': '中午',
    'afternoon': '下午',
    'evening': '晚上',
    'night': '睡前',
}


class UserTask(models.Model):
    """一条日常任务（也可以是一条「routine」：每天/每周重复的那组事）"""

    KIND_CHOICES = [
        ('once', '一次性'),
        ('routine', '日常'),
    ]
    FREQUENCY_CHOICES = [
        ('once', '一次性'),
        ('quota', '配额制'),
        ('habit', '习惯养成'),
    ]
    QUOTA_PERIOD_CHOICES = [
        ('week', '每周 N 次'),
        ('day', '每 N 天一次'),
    ]
    PERSIST_CHOICES = [
        ('streak', '连续（断了要记录断）'),
        ('cumulative', '累计（做几次算几次）'),
    ]
    STATUS_CHOICES = [
        ('active', '进行中'),
        ('done', '已完成'),
        ('archived', '已归档'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks',
        verbose_name='用户',
    )
    title = models.CharField('任务标题', max_length=100)
    description = models.TextField('描述', blank=True)

    # 快照来源：SET_NULL 而不是 CASCADE —— 模板被删/下架不应该把用户建好的任务一起删掉
    source_pattern = models.ForeignKey(
        'quick.QuickPattern', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='user_tasks', verbose_name='来源模板',
    )

    # kind 是「大分类」（列表页按这个分组/筛选），frequency_type 是「具体频率」。
    # 两个字段并存是 spec 的要求：kind 给 UI 用，frequency_type 给排期/提醒用。
    kind = models.CharField('类型', max_length=10, choices=KIND_CHOICES, default='once')
    frequency_type = models.CharField('频率', max_length=10, choices=FREQUENCY_CHOICES, default='once')

    # 仅 quota 用：一周 N 次（period=week）或 N 天一次（period=day）
    quota_period = models.CharField('配额周期', max_length=10, choices=QUOTA_PERIOD_CHOICES, blank=True)
    quota_count = models.PositiveIntegerField('配额次数', null=True, blank=True)

    # 连续 vs 累计：streak 断了要留记录（打卡表），cumulative 只累加不惩罚
    persist = models.CharField('坚持方式', max_length=12, choices=PERSIST_CHOICES, default='cumulative')

    # 目标/完成次数：once=剩余次数；quota=本周期剩余次数；留空=不限次数
    target_count = models.PositiveIntegerField(
        '目标次数', null=True, blank=True, help_text='once=剩余次数；quota=本周期剩余；留空=不限',
    )
    done_count = models.PositiveIntegerField('已完成次数', default=0)

    # t-box 时间段：morning/noon/afternoon/evening/night，或用户自己写（"通勤时"）
    timeslot = models.CharField(
        '时间段', max_length=20, blank=True,
        help_text='建议值见 models.TIMESLOT_ORDER；也可以自定义，如「通勤时」',
    )

    # 预留字段（#079 明确本轮不实现计算，先留位，nullable）
    expected_at = models.DateTimeField(
        '预期完成时间', null=True, blank=True, help_text='用户填，用来让系统算 deadline',
    )
    deadline = models.DateTimeField(
        '截止时间', null=True, blank=True, help_text='系统按 expected_at 算出来的截止时间',
    )

    # #085：任务排到哪一天（大周期日程用）。
    # null = 没排期："今日任务"照常显示，只是时间轴上没有它的格子。
    # 用 DateField 而不是 DateTime —— 日程按"天"聚合，不需要钟点。
    plan_date = models.DateField(
        '计划日期', null=True, blank=True,
        help_text='任务排到哪一天；空 = 还没排期',
    )

    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='active')

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '日常任务'
        verbose_name_plural = '日常任务'
        ordering = ['-updated_at']
        indexes = [
            # 「我的任务」列表：按用户 + 状态过滤
            models.Index(fields=['user', 'status'], name='task_user_status_idx'),
            # 日程页：按用户 + 时间段分组
            models.Index(fields=['user', 'timeslot'], name='task_user_slot_idx'),
            # #085：时间轴按"某天有哪些任务"查（日/周/月三档都落在这个范围扫描上）
            models.Index(fields=['user', 'plan_date'], name='task_user_plan_idx'),
        ]

    def __str__(self):
        return self.title

    def get_timeslot_label(self):
        """时间段的中文名；自定义值原样返回"""
        return TIMESLOT_LABELS.get(self.timeslot, self.timeslot)

    @property
    def progress(self):
        """完成步骤数 / 总步骤数（#079：先按平均权重，以后要再加权）。

        用一次 aggregate 算完，避免 Step 2 的列表接口出现 N+1；
        真到列表页要更快，可以在 queryset 上 annotate 后由视图覆盖。
        """
        agg = self.steps.aggregate(
            total=models.Count('id'),
            done=models.Count('id', filter=models.Q(is_done=True)),
        )
        total = agg['total'] or 0
        if total <= 0:
            return 0.0
        return round((agg['done'] or 0) / total, 4)

    @property
    def remaining_count(self):
        """还剩几次；target_count 为空表示不限次数，返回 None

        #087：quota 的剩余次数改成【按周期】算（TaskDay 计数），不再拿历史累计的 done_count 减 ——
        done_count 从不清零，用几周后会把它减成 0 甚至负数，那就是"永远不准"的根源。
        """
        if self.frequency_type == 'once':
            # 一次性任务：没做完就还剩 1 次，做完（status=done）就是 0。
            # 放在 target_count 判空之前：#088 之前建的 once 任务 target_count 是空的，
            # 走到下面会返回 None，界面就把"一次性"显示成"不限次数"（测试抓到过）。
            return 0 if self.status == 'done' else 1
        if self.target_count is None:
            return None
        if self.frequency_type == 'quota' and self.quota_count:
            used = self.period_done_count()
            return max(self.quota_count - used, 0)
        return max(self.target_count - self.done_count, 0)

    def period_done_count(self, today=None):
        """#087：本周期内"完成过几次"（按 TaskDay 里 completed=True 的天数算）。

        quota_period=week → 本周（周一起）；quota_period=day → 近 quota_count 天。
        日期一律用 timezone.localtime(...).date()，避免 UTC 跨天错位。
        """
        today = today or local_today()
        if self.quota_period == 'week':
            start = today - timedelta(days=today.weekday())
        else:
            span = max(int(self.quota_count or 1), 1)
            start = today - timedelta(days=span - 1)
        return self.days.filter(date__gte=start, date__lte=today, completed=True).count()

    def day_for(self, on_date=None):
        """取某天的 TaskDay（默认今天）；没有就返回 None"""
        on_date = on_date or local_today()
        return self.days.filter(date=on_date).first()


def local_today():
    """#087：服务器本地日期。

    settings.TIME_ZONE = Asia/Shanghai，USE_TZ=True 时 timezone.now() 是 UTC，
    直接取 .date() 在晚上 8 点之后就会算成"明天"——所以统一走 localtime。
    """
    return timezone.localtime(timezone.now()).date()


def today_tasks(user, on_date=None):
    """「今天的任务」的**唯一定义**（#089）。

    为什么要有这个函数：以前三处各写各的 ——
      任务页「今天 x/y」= status=active 全部（连排到 2030 的都算），
      日程页「今天」= plan_date == 今天，
      未排期 = plan_date 为空。
    结果：任务排到明年也算"今天"，allDone 永远不成立，顶部永远挂"还有 N 项"，
    而日程页说今天没事 —— 同一个词两个意思，用户一眼就看出不对。

    定死（#089 spec）：
      今天的任务 = status='active' 且 plan_date == 今天
      · 未来任务（plan_date > 今天）不算今天
      · 没排期（plan_date 为空）单独一栏，不算今天
      · 加入任务时默认 plan_date = 今天（所以新加的照常出现在今天）

    任务页 / 日程页 / allDone 都必须走这里，别再写第二份条件。
    """
    return UserTask.objects.filter(
        user=user,
        status='active',
        plan_date=on_date or local_today(),
    )


class TaskDay(models.Model):
    """#087：某个任务在【某一天】的完成情况（一天一条，做过的才有）

    为什么加这张表：UserTaskStep.is_done 是全局布尔，没有"哪天"的维度，
    导致昨天勾的勾到今天还在，界面显示"今天全清了"但其实今天什么都没做。
    TaskDay 同时解决：每日重置 + 历史 + 连续天数(streak) + 日历完成度。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='task_days', verbose_name='用户',
    )
    task = models.ForeignKey(
        UserTask, on_delete=models.CASCADE, related_name='days', verbose_name='任务',
    )
    date = models.DateField('日期')
    # 当天勾掉了哪些步骤（存 id 数组：步骤后来改名/改顺序都不影响；步骤删了就按现存步骤算交集）
    done_step_ids = models.JSONField('当天完成的步骤 id', default=list, blank=True)
    done_count = models.PositiveIntegerField('当天完成步数', default=0)
    # 当天是否把这整张做完了（quota 的"本周期做了几次"、日历的"这格完成了"都靠它）
    completed = models.BooleanField('当天全部完成', default=False)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '任务日流水'
        verbose_name_plural = '任务日流水'
        ordering = ['-date']
        constraints = [
            # 一个任务一天只有一条
            models.UniqueConstraint(fields=['task', 'date'], name='task_day_unique'),
        ]
        indexes = [
            # 日历/连续天数：按用户 + 日期范围扫
            models.Index(fields=['user', 'date'], name='task_day_user_date_idx'),
        ]

    def __str__(self):
        return f'{self.task_id}@{self.date} {self.done_count}'


class UserTaskStep(models.Model):
    """任务里的一个步骤（建任务时从 QuickStep 复制的快照）

    字段口径跟 quick.QuickStep 对齐（title / instruction / explain / duration_seconds），
    这样执行页的适配器（utils/adapter.js: toStepData）可以直接吃，不用再写一套映射。
    """

    task = models.ForeignKey(
        UserTask, on_delete=models.CASCADE, related_name='steps', verbose_name='所属任务',
    )
    order = models.PositiveIntegerField('顺序', default=0)
    title = models.CharField('步骤标题', max_length=100)
    instruction = models.TextField('画面文字', blank=True)
    explain = models.TextField('为什么这么做', blank=True)
    duration_seconds = models.PositiveIntegerField('时长（秒）', default=0, help_text='0 = 手动推进')
    # #079 Step 2：对齐 quick.QuickStep ——「给了建议时长」不等于「必须倒计时」
    # （"擦三下"这种 30 秒提示语不该起倒计时），所以单独一个布尔，不靠时长推断
    is_timed = models.BooleanField('需要倒计时', default=False, help_text='True 才走倒计时')
    # #079 Step 2：拆步骤进日程时回指来源；SET_NULL = 模板步骤删了只断来源，任务照旧
    source_step = models.ForeignKey(
        'quick.QuickStep', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='task_copies', verbose_name='来源步骤',
    )

    # 用户填报：勾上就是完成，取消勾要同时清掉 done_at
    is_done = models.BooleanField('已完成', default=False)
    done_at = models.DateTimeField('完成时间', null=True, blank=True)

    class Meta:
        verbose_name = '任务步骤'
        verbose_name_plural = '任务步骤'
        ordering = ['order']

    def __str__(self):
        return f'{self.order}. {self.title}'
