import secrets

from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    username = None  # 不用 username，用 email 登录
    email = models.EmailField('邮箱', unique=True)
    avatar = models.ImageField('头像', upload_to='avatars/', blank=True, null=True)
    # #071："我的"页资料区可编辑的昵称。为空时对外统一显示「行动锚用户」（#070 的作者名规则）。
    nickname = models.CharField('昵称', max_length=30, blank=True)
    interest_tags = models.CharField('兴趣标签', max_length=255, blank=True, help_text='逗号分隔')
    theme = models.CharField('主题', max_length=30, default='warm',
        help_text='界面配色主题')
    # #057①：api_token 加唯一约束。它等同于登录态（`Authorization: Token <x>`），
    # 不唯一时理论上两个账号可能撞到同一个 token（谁先被查到就登录成谁）。
    # 历史行里可能有空串/重复值，靠 users/0006 的数据迁移先补齐去重再加约束。
    api_token = models.CharField('API令牌', max_length=64, blank=True, unique=True)
    # 微信 openid：小程序登录后才写入；网页邮箱用户为 NULL（Postgres 下 NULL 不参与唯一冲突）
    openid = models.CharField('微信openid', max_length=64, blank=True, null=True, unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # token 为空时自动生成，覆盖 allauth 注册/登录、管理员、shell 等所有创建入口
        if not self.api_token:
            self.api_token = secrets.token_hex(32)
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                # 调用方只更新部分字段（如登录时 last_login）也要把 token 一并落库
                kwargs['update_fields'] = set(update_fields) | {'api_token'}
        super().save(*args, **kwargs)