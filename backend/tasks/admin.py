"""后台：让 Jeff 不写代码也能看/改任务（#079 Step 1 只建表，先把可观测性做好）"""

from django.contrib import admin

from .models import UserTask, UserTaskStep


class UserTaskStepInline(admin.TabularInline):
    model = UserTaskStep
    extra = 0
    ordering = ['order']
    fields = ['order', 'title', 'duration_seconds', 'is_done', 'done_at']


@admin.register(UserTask)
class UserTaskAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'user', 'kind', 'frequency_type', 'timeslot',
        'done_count', 'target_count', 'status', 'progress_display', 'updated_at',
    ]
    list_filter = ['status', 'kind', 'frequency_type', 'persist', 'timeslot']
    search_fields = ['title', 'description', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [UserTaskStepInline]
    list_select_related = ['user']

    @admin.display(description='进度')
    def progress_display(self, obj):
        return f'{obj.progress:.0%}'


@admin.register(UserTaskStep)
class UserTaskStepAdmin(admin.ModelAdmin):
    list_display = ['task', 'order', 'title', 'duration_seconds', 'is_done', 'done_at']
    list_filter = ['is_done']
    search_fields = ['title', 'instruction', 'task__title']
    list_select_related = ['task']
