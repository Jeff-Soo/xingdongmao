"""Admin 首页看板的模板标签：把 api.admin_views.dashboard_stats() 的数据渲染成一块面板。"""
from django import template

from api.admin_views import dashboard_stats

register = template.Library()


@register.inclusion_tag('admin/dashboard_panel.html')
def dashboard_panel():
    return dashboard_stats()
