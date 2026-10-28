from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from quick.models import QuickPattern

from .models import User


class EmailUserCreationForm(BaseUserCreationForm):
    """本项目的用户没有 username，用邮箱当账号——Admin「增加用户」用这个表单"""

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ('email',)


class QuickPatternInline(admin.TabularInline):
    """用户详情页直接看他发布的模板（只读，点标题进模板编辑页）"""

    model = QuickPattern
    extra = 0
    fields = ('title', 'status', 'usage_count', 'avg_rating', 'created_at')
    readonly_fields = ('title', 'status', 'usage_count', 'avg_rating', 'created_at')
    can_delete = False
    show_change_link = True
    ordering = ('-created_at',)

    def has_add_permission(self, request, obj=None):
        # 模板只在"创建模板"里加，后台不给凭空建
        return False


# ===== 批量动作：封禁 / 解封 =====

@admin.action(description='① 封禁（禁止登录，其内容需另行下架）')
def ban_users(modeladmin, request, queryset):
    # 别把管理员（或自己）一起封了，否则没人能再进后台
    targets = queryset.exclude(is_superuser=True).exclude(pk=request.user.pk)
    n = targets.update(is_active=False)
    skipped = queryset.count() - n
    msg = f'已封禁 {n} 个账号' + (f'；跳过 {skipped} 个管理员账号（防止把自己锁在门外）' if skipped else '')
    modeladmin.message_user(request, msg)


@admin.action(description='② 解封（恢复登录）')
def unban_users(modeladmin, request, queryset):
    n = queryset.update(is_active=True)
    modeladmin.message_user(request, f'已解封 {n} 个账号')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """自定义用户后台。

    注意：django.contrib.auth.admin 注册的是内置 auth.User（本项目已用 users.User 替换，
    那个注册会被跳过），所以自定义用户必须在这里自己注册。
    """

    list_display = ('email', 'joined_display', 'patterns_link', 'last_login_display', 'banned_state')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'openid')
    ordering = ('-date_joined',)
    actions = [ban_users, unban_users]
    inlines = [QuickPatternInline]
    add_form = EmailUserCreationForm
    # BaseUserAdmin 默认的 filter_horizontal 指向 groups/user_permissions，
    # 而 v1 不做权限体系、fieldsets 里没有它们，留着会报错
    filter_horizontal = ()

    # BaseUserAdmin 默认 fieldsets 引用了 username，自定义用户没有这个字段 → 必须自己写
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('账号状态', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('微信 / 令牌', {'fields': ('openid', 'api_token')}),
        ('资料', {'fields': ('avatar', 'theme', 'interest_tags')}),
        ('时间', {'fields': ('last_login', 'date_joined')}),
        ('他发布的模板', {'fields': ('patterns_link_detail',)}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),
    )

    readonly_fields = ('openid', 'api_token', 'last_login', 'date_joined', 'patterns_link_detail')

    def get_queryset(self, request):
        # 列表页要显示发布数，一次聚合掉，别每行查一次
        return super().get_queryset(request).annotate(pattern_count=Count('quickpattern'))

    def get_inline_instances(self, request, obj=None):
        # 新增用户时还没有模板可看，不渲染 inline（否则新增表单会带上 inline 的管理字段）
        return [] if obj is None else super().get_inline_instances(request, obj)

    @admin.display(description='发布模板数', ordering='pattern_count')
    def patterns_link(self, obj):
        n = getattr(obj, 'pattern_count', None)
        if n is None:
            n = obj.quickpattern_set.count()
        url = reverse('admin:quick_quickpattern_changelist') + f'?author__id__exact={obj.pk}'
        return format_html('<a href="{}">{}</a>', url, n)

    @admin.display(description='他发布的模板')
    def patterns_link_detail(self, obj):
        if not obj or not obj.pk:
            return '保存后可见'
        url = reverse('admin:quick_quickpattern_changelist') + f'?author__id__exact={obj.pk}'
        n = obj.quickpattern_set.count()
        return format_html('<a href="{}">在模板列表里查看他发布的 {} 个模板 →</a>', url, n)

    # 下面三个是为了让列名直接说人话（Django 默认列名是「加入日期 / 上次登录 / 有效」）
    @admin.display(description='注册时间', ordering='date_joined')
    def joined_display(self, obj):
        return obj.date_joined

    @admin.display(description='最后登录', ordering='last_login')
    def last_login_display(self, obj):
        return obj.last_login or '从未登录'

    @admin.display(description='是否封禁', ordering='is_active')
    def banned_state(self, obj):
        if obj.is_active:
            return format_html('<span style="color:#2e8b57;">{}</span>', '正常')
        return format_html('<span style="color:#ba2121;font-weight:700;">{}</span>', '已封禁')
