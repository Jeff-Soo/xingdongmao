from django.db import models
from django.conf import settings


class QuickPatternQuerySet(models.QuerySet):
    """#056：对外可见的**唯一 queryset 口径**（列表/标签/联想/收藏/看板/分享图都用它）。"""

    def visible(self):
        return self.filter(is_listed=True, is_reported=False)


class QuickPattern(models.Model):
    """执行引导模板（生活事务 / 职业规范 / 通用流程）"""
    CATEGORY_CHOICES = [
        ('life_out', '出行准备'),
        ('life_home', '居家事务'),
        ('life_daily', '日常事务'),
        ('work_service', '服务行业'),
        ('work_office', '职场办公'),
        ('work_safety', '安全操作'),
        ('other', '其他'),
    ]
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('published', '社区验证中'),
        ('verified', '社区推荐'),
        ('reported', '待复核'),
    ]

    # #056：自定义 manager，提供 .visible() 统一可见性口径
    objects = QuickPatternQuerySet.as_manager()

    title = models.CharField('标题', max_length=100)
    tagline = models.CharField('一句话效果', max_length=200, blank=True,
        help_text='如"出门前扫一遍，回头拿钥匙最烦"')
    description = models.TextField('描述', blank=True)
    category = models.CharField('分类', max_length=20, choices=CATEGORY_CHOICES, default='other')
    icon = models.CharField('图标', max_length=5, default='🧠',
        help_text='老字段：存 emoji（不同系统字形/配色不可控），仅作 icon_key 缺失时的回退')
    # #073：图标改成"语义 slug"（house/package/utensils…），前端按 slug 画矢量图标；
    # 保留 icon 字段是为了不让老数据和老客户端直接变空白，迁移时会把 emoji 映射成 slug
    icon_key = models.CharField('图标名', max_length=32, blank=True,
        help_text='矢量图标 slug，取值见 xingdongmao/utils/icons.js 的 PICKER_ICONS')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='作者')
    is_official = models.BooleanField('官方模板', default=False)
    allow_fork = models.BooleanField('允许 Fork 修改', default=True)
    usage_count = models.PositiveIntegerField('使用次数', default=0)
    avg_rating = models.FloatField('平均评分', default=0)  # 0-5
    rating_count = models.PositiveIntegerField('评分数', default=0)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')
    # #051：「上架」和「验证」是两个独立维度，各自一个布尔字段。
    # status 退化为"派生出来的展示值"（由 is_listed / is_verified / is_reported 推出），
    # 只为了兼容前端和旧代码；判断公开/推荐一律看这两个布尔。
    is_listed = models.BooleanField('已上架', default=False,
        help_text='对外公开可见的唯一判据（草稿/下架都为 False）')
    is_verified = models.BooleanField('已验证', default=False,
        help_text='社区推荐（可人工标，也可用量+评分自动转正）；未上架时不给标')
    is_reported = models.BooleanField('被举报', default=False)
    fork_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='forks', verbose_name='Fork 来源')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '引导模板'
        verbose_name_plural = '引导模板'
        ordering = ['-is_official', '-usage_count']

    def __str__(self):
        return self.title

    def avg_stars(self):
        """从 ratings 计算均分并更新 avg_rating / rating_count"""
        ratings = self.ratings.all()
        count = ratings.count()
        self.rating_count = count
        self.avg_rating = round(sum(r.stars for r in ratings) / count, 2) if count else 0
        self.save(update_fields=['avg_rating', 'rating_count'])
        return self.avg_rating

    def check_verify(self):
        """满足转正条件则转 verified，返回当前状态"""
        if (self.is_listed and self.usage_count >= 10
                and self.rating_count >= 3 and self.avg_rating >= 4.0):
            self.is_verified = True
            self.sync_legacy_status()
            self.save(update_fields=['is_verified', 'status'])
        return self.status

    def sync_legacy_status(self):
        """把两个独立维度折算回 status（只给旧界面/旧接口看）。

        下架(is_reported) > 已验证(is_verified) > 已上架(is_listed) > 草稿。
        """
        if self.is_reported:
            self.status = 'reported'
        elif self.is_verified:
            self.status = 'verified'
        elif self.is_listed:
            self.status = 'published'
        else:
            self.status = 'draft'
        return self.status

    def can_view(self, user=None):
        """#054：可见性的**唯一判据**（列表 / 详情 / 分享图都该走这里）。

        - 已上架（且未被下架）→ 任何人都能读，含未登录；
        - 未上架或被下架 → 只有作者本人能读。
        以前各处各写各的（列表看 is_listed、详情看旧 status），口径一漂就出现
        "列表里看得见、点进去说模板不存在" —— 所以收敛到这一个方法。
        """
        if self.is_listed and not self.is_reported:
            return True
        uid = getattr(user, 'pk', None)
        return bool(uid is not None and uid == self.author_id)


class QuickStep(models.Model):
    """引导步骤"""
    pattern = models.ForeignKey(QuickPattern, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField('顺序', default=0)
    title = models.CharField('步骤标题', max_length=100)
    instruction = models.TextField('画面文字')
    explain = models.TextField('为什么这么做', blank=True,
        help_text='展开后显示的详细解释，说明这么做的原因')
    duration_seconds = models.PositiveIntegerField('时长（秒）', default=30, help_text='0 = 手动推进')
    is_timed = models.BooleanField('需要计时', default=False, help_text='需要倒计时的步骤标 True')

    class Meta:
        verbose_name = '引导步骤'
        verbose_name_plural = '引导步骤'
        ordering = ['order']

    def __str__(self):
        return f'{self.order}. {self.title}'


class QuickRating(models.Model):
    """用户对模板的评分"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pattern = models.ForeignKey(QuickPattern, on_delete=models.CASCADE, related_name='ratings')
    stars = models.PositiveIntegerField('星级', default=5)
    created_at = models.DateTimeField('评分时间', auto_now_add=True)

    class Meta:
        verbose_name = '评分'
        verbose_name_plural = '评分'
        constraints = [
            models.UniqueConstraint(fields=['user', 'pattern'], name='unique_user_pattern_rating'),
        ]


class QuickNote(models.Model):
    """用户完成后的反思笔记"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pattern = models.ForeignKey(QuickPattern, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField('以后我会怎么做', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '反思笔记'
        verbose_name_plural = '反思笔记'
        ordering = ['-created_at']


class QuickUsage(models.Model):
    """用户执行记录——评分前校验是否真实执行过"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pattern = models.ForeignKey(QuickPattern, on_delete=models.CASCADE, related_name='usages')
    used_at = models.DateTimeField('执行时间', auto_now_add=True)

    class Meta:
        verbose_name = '执行记录'
        verbose_name_plural = '执行记录'
        ordering = ['-used_at']


class QuickFavorite(models.Model):
    """用户收藏模板（限一次）"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pattern = models.ForeignKey(QuickPattern, on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField('收藏时间', auto_now_add=True)

    class Meta:
        verbose_name = '收藏'
        verbose_name_plural = '收藏'
        constraints = [
            models.UniqueConstraint(fields=['user', 'pattern'], name='unique_user_pattern_favorite'),
        ]


class QuickView(models.Model):
    """#071 浏览记录：谁最近看过哪个模板（"我的"页按时间倒序展示）。

    规格书里叫 UserView，这里按 quick 应用自己的命名习惯叫 QuickView（同一张表的意思）。

    只记【公开可见】的模板：草稿、被下架的都不记（判断放在 views 里，模型不掺业务）。
    同一用户同一模板只留一行，重看就刷新 viewed_at —— 这样"最近看过"列表天然去重、
    表也不会被反复翻看的记录撑大。
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pattern = models.ForeignKey(QuickPattern, on_delete=models.CASCADE, related_name='views')
    viewed_at = models.DateTimeField('最近查看时间', auto_now=True)

    class Meta:
        verbose_name = '浏览记录'
        verbose_name_plural = '浏览记录'
        ordering = ['-viewed_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'pattern'], name='unique_user_pattern_view'),
        ]
