from django.db import models
from django.conf import settings


class Pattern(models.Model):
    """模板"""
    DIFFICULTY_CHOICES = [
        ('easy', '简单'),
        ('medium', '中等'),
        ('hard', '困难'),
    ]

    BURDEN_CHOICES = [
        ('zero_gear', '零器械'),
        ('interruptible', '可中断'),
        ('full_focus', '需专注'),
    ]
    burden = models.CharField('心理负担', max_length=20, choices=BURDEN_CHOICES,
        default='full_focus', blank=True)
    
    title = models.CharField('标题', max_length=200)
    description = models.TextField('描述', blank=True)
    category = models.CharField('分类', max_length=100, blank=True)
    tags = models.CharField('标签', max_length=255, blank=True, help_text='逗号分隔')
    difficulty = models.CharField('难度', max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='作者')
    fork_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='衍生自')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '模板'
        verbose_name_plural = '模板'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_tags_list(self):
        """将逗号分隔的标签字符串转为列表，供模板使用"""
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]


class TimeBlock(models.Model):
    """时间块"""
    pattern = models.ForeignKey(Pattern, on_delete=models.CASCADE, related_name='time_blocks', verbose_name='所属模板')
    order = models.PositiveIntegerField('顺序', default=0)
    # ---------- 改动 1：让固定时间可为空 ----------
    start_time = models.TimeField('开始时间', null=True, blank=True)
    end_time = models.TimeField('结束时间', null=True, blank=True)

    action = models.CharField('动作', max_length=255)
    notes = models.TextField('备注', blank=True)

    # ---------- 改动 2：增加浮动相关字段 ----------
    is_floating = models.BooleanField(
        '浮动时间',
        default=False,
        help_text='勾选后时间不固定，用标签代替如"通勤时""午休时"'
    )
    floating_label = models.CharField(
        '浮动标签',
        max_length=50,
        blank=True,
        help_text='如"通勤时""午休时""睡前"'
    )
    alt_action = models.CharField('备选动作', max_length=255, blank=True,
        help_text='轻松模式下的替代动作，如"散步"替代"跑步5公里"')
    alt_duration_minutes = models.PositiveIntegerField('缩短时长（分钟）', null=True, blank=True,
        help_text='轻松模式下该时间块缩短为多少分钟，如 30 分钟缩短为 15 分钟')

    class Meta:
        verbose_name = '时间块'
        verbose_name_plural = '时间块'
        ordering = ['order']

    def __str__(self):
        if self.is_floating:
            return f'🔄 {self.floating_label or self.action}'
        start = self.start_time.strftime('%H:%M') if self.start_time else '--:--'
        end = self.end_time.strftime('%H:%M') if self.end_time else '--:--'
        return f'{start}-{end} {self.action}'
    
class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pattern = models.ForeignKey(Pattern, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'pattern']

class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pattern = models.ForeignKey(Pattern, on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'pattern']