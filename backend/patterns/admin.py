from django.contrib import admin
from .models import Pattern, TimeBlock


class TimeBlockInline(admin.TabularInline):
    model = TimeBlock
    extra = 5
    ordering = ['order']


@admin.register(Pattern)
class PatternAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'difficulty', 'author', 'created_at']
    list_filter = ['difficulty', 'category']
    search_fields = ['title', 'description']
    inlines = [TimeBlockInline]


@admin.register(TimeBlock)
class TimeBlockAdmin(admin.ModelAdmin):
    list_display = ['pattern', 'start_time', 'end_time', 'action', 'order']
    list_filter = ['pattern']