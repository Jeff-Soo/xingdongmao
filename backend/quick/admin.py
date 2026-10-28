import json
from datetime import timedelta

from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from .batch_import import PROMPT_TEXT, import_templates, parse_templates
from .models import QuickPattern, QuickStep, QuickRating, QuickNote, QuickUsage, QuickFavorite

# 后台首页换成带监控看板的版本（模板 extends 原生 admin/index.html，只多一块统计，见 templates/admin/dashboard_index.html）
admin.site.index_template = 'admin/dashboard_index.html'


class QuickStepInline(admin.TabularInline):
    model = QuickStep
    extra = 0
    fields = ('order', 'title', 'instruction', 'explain', 'duration_seconds', 'is_timed')


class CreatedRangeFilter(admin.SimpleListFilter):
    """创建时间：今天 / 本周 / 本月——出事时最常按"最近"翻"""

    title = '创建时间'
    parameter_name = 'created_range'

    def lookups(self, request, model_admin):
        return (('today', '今天'), ('week', '本周'), ('month', '本月'))

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == 'today':
            return queryset.filter(created_at__date=today)
        if self.value() == 'week':
            return queryset.filter(created_at__date__gte=today - timedelta(days=today.weekday()))
        if self.value() == 'month':
            return queryset.filter(created_at__date__gte=today.replace(day=1))
        return queryset


# ===== 批量动作：应急处置就靠这几个（勾选后右上角"动作"里选）=====
# #051：上架 / 验证 是两个独立维度——is_listed（对外可见）与 is_verified（社区推荐）。
# status 只是折算出来的展示值（QuickPattern.sync_legacy_status）。

class ListedFilter(admin.SimpleListFilter):
    """上架状态（对外是否可见）"""
    title = '上架状态'
    parameter_name = 'listed'

    def lookups(self, request, model_admin):
        return (('yes', '已上架'), ('no', '未上架'))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_listed=True)
        if self.value() == 'no':
            return queryset.filter(is_listed=False)
        return queryset


class VerifiedFilter(admin.SimpleListFilter):
    """验证状态（是否已标社区推荐）"""
    title = '验证状态'
    parameter_name = 'verified'

    def lookups(self, request, model_admin):
        return (('yes', '已验证'), ('no', '未验证'))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_verified=True)
        if self.value() == 'no':
            return queryset.filter(is_verified=False)
        return queryset


@admin.action(description='① 上架（对外公开可见）')
def put_on_shelf(modeladmin, request, queryset):
    n = queryset.update(is_listed=True, is_reported=False)
    for qp in queryset:
        qp.sync_legacy_status()
        qp.save(update_fields=['status'])
    modeladmin.message_user(request, f'已上架 {n} 个模板（对外可见）')


@admin.action(description='② 下架（移出公开列表，对外立即消失）')
def take_down(modeladmin, request, queryset):
    n = queryset.update(is_listed=False, is_reported=True)
    for qp in queryset:
        qp.sync_legacy_status()
        qp.save(update_fields=['status'])
    modeladmin.message_user(request, f'已下架 {n} 个模板（对外不可见，验证状态保留）')


@admin.action(description='③ 标为社区推荐（需先上架）')
def mark_verified(modeladmin, request, queryset):
    """#051：只有已上架的才能标推荐；未验证不影响（Jeff 明确"未验证也可推荐"）。"""
    blocked = queryset.filter(is_listed=False)
    allowed = queryset.filter(is_listed=True)
    n = allowed.update(is_verified=True, is_reported=False)
    for qp in allowed:
        qp.sync_legacy_status()
        qp.save(update_fields=['status'])
    if blocked.exists():
        modeladmin.message_user(
            request,
            f'已把 {n} 个模板标为社区推荐；另有 {blocked.count()} 个【未上架】的没标成功——请先上架再推荐',
            level=messages.WARNING)
    else:
        modeladmin.message_user(request, f'已把 {n} 个模板标为社区推荐')


@admin.action(description='④ 取消推荐')
def unmark_verified(modeladmin, request, queryset):
    n = queryset.update(is_verified=False)
    for qp in queryset:
        qp.sync_legacy_status()
        qp.save(update_fields=['status'])
    modeladmin.message_user(request, f'已取消 {n} 个模板的推荐')


@admin.action(description='⑤ 忽略举报（内容没问题）')
def clear_report(modeladmin, request, queryset):
    n = queryset.update(is_reported=False)
    for qp in queryset:
        qp.sync_legacy_status()
        qp.save(update_fields=['status'])
    modeladmin.message_user(request, f'已忽略 {n} 条举报')


@admin.register(QuickPattern)
class QuickPatternAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'is_listed', 'is_verified', 'status', 'usage_count', 'avg_rating', 'rating_count', 'is_reported', 'created_at')
    # author 用 RelatedOnlyFieldListFilter：用户详情页的"他发布的模板"链接靠它生效
    # #051：右侧过滤面板加了"上架状态 / 验证状态"两个独立维度
    list_filter = (ListedFilter, VerifiedFilter, 'status', 'is_reported',
                   ('author', admin.RelatedOnlyFieldListFilter), CreatedRangeFilter)
    list_editable = ('is_listed', 'is_verified')
    search_fields = ('title', 'tagline', 'author__email')
    list_select_related = ('author',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    inlines = [QuickStepInline]
    # 这三个是程序算出来的，手改容易和真实数据对不上
    readonly_fields = ('usage_count', 'avg_rating', 'rating_count')
    # ⚠️ 动作必须出现在这个列表里才会进"动作"下拉菜单：
    # #051 加了 put_on_shelf / unmark_verified 两个函数，但漏了登记，菜单里就一直没有「上架」——
    # 以后再加动作，记得同时加到这里（列表顺序 = 菜单里显示的顺序）。
    actions = [put_on_shelf, take_down, mark_verified, unmark_verified, clear_report]

    def save_model(self, request, obj, form, change):
        """#054：后台直接改 is_listed / is_verified（含列表页行内勾选）时把派生的
        status 一并折算好 —— 否则 status 会漂，详情接口/旧界面就会错判可见性。"""
        obj.sync_legacy_status()
        super().save_model(request, obj, form, change)

    # ===== #046 内部批量导入页：/admin/quick/batch-import/ =====
    # admin_view 只放 is_staff（且 is_active）的登录用户进来 → 普通用户连页面地址都打不开；
    # 接口那边另有 require_staff 403 兜底，两条路都不给普通用户。
    def get_urls(self):
        extra = [
            path('batch-import/', self.admin_site.admin_view(self.batch_import_view), name='quick_batch_import'),
        ]
        return extra + super().get_urls()

    def batch_import_view(self, request):
        result = None
        error = None
        raw = ''
        if request.method == 'POST':
            raw = request.POST.get('payload', '')
            try:
                templates = parse_templates(json.loads(raw or '{}'))
            except json.JSONDecodeError as exc:
                error = f'JSON 解析失败：{exc}'
            except ValueError as exc:
                error = str(exc)
            else:
                result = import_templates(templates, author=request.user, is_official=True)
                result['total'] = len(templates)
        context = dict(
            self.admin_site.each_context(request),
            title='批量导入模板',
            prompt=PROMPT_TEXT,
            result=result,
            error=error,
            raw=raw,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/quick/batch_import.html', context)


@admin.register(QuickRating)
class QuickRatingAdmin(admin.ModelAdmin):
    list_display = ('pattern', 'user', 'stars', 'created_at')
    list_filter = ('stars',)
    search_fields = ('pattern__title', 'user__email')
    ordering = ('-created_at',)


@admin.register(QuickNote)
class QuickNoteAdmin(admin.ModelAdmin):
    list_display = ('pattern', 'user', 'created_at')
    search_fields = ('pattern__title', 'user__email', 'content')
    ordering = ('-created_at',)


@admin.register(QuickUsage)
class QuickUsageAdmin(admin.ModelAdmin):
    list_display = ('pattern', 'user', 'used_at')
    search_fields = ('pattern__title', 'user__email')
    ordering = ('-used_at',)


@admin.register(QuickFavorite)
class QuickFavoriteAdmin(admin.ModelAdmin):
    list_display = ('pattern', 'user', 'created_at')
    search_fields = ('pattern__title', 'user__email')
    ordering = ('-created_at',)
