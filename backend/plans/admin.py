from django.contrib import admin
from .models import UserPlan, UserPlanBlock


class UserPlanBlockInline(admin.TabularInline):
    model = UserPlanBlock
    extra = 1
    ordering = ['order']


@admin.register(UserPlan)
class UserPlanAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'pattern', 'activated_date', 'created_at']
    list_filter = ['activated_date']
    search_fields = ['title', 'user__email']
    inlines = [UserPlanBlockInline]


@admin.register(UserPlanBlock)
class UserPlanBlockAdmin(admin.ModelAdmin):
    list_display = ['plan', 'start_time', 'end_time', 'action', 'order', 'is_completed']
    list_filter = ['is_completed', 'plan']