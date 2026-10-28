from django.urls import path
from . import views

app_name = 'plans'

urlpatterns = [
    path('', views.plan_list, name='plan_list'),
    path('<int:pk>/', views.plan_edit, name='plan_edit'),
    path('fork/<int:pattern_pk>/', views.fork_pattern, name='fork_pattern'),
    path('execute/<int:pk>/', views.plan_execute, name='plan_execute'),
    path('activate/<int:pk>/', views.activate_plan, name='activate_plan'),
    path('move/<int:pk>/<str:direction>/', views.move_block, name='move_block'),
    path('complete/<int:pk>/', views.complete_block, name='complete_block'),
    path('undo/<int:pk>/', views.undo_block, name='undo_block'),
    path('end-today/', views.end_today, name='end_today'),
    path('inline-edit/<int:pk>/', views.inline_edit_block, name='inline_edit_block'),
    path('<int:pk>/toggle_enabled/', views.toggle_enabled, name='toggle_enabled'),
    path('<int:pk>/delete/', views.delete_plan, name='delete_plan'),
    path('save_mood/', views.save_mood, name='save_mood'),
    path('calendar/', views.calendar_view, name='calendar_view'),
    path('calendar/data/', views.calendar_data, name='calendar_data'),
    path('day/<int:pk>/', views.day_detail, name='day_detail'),
    path('lazy-mode/', views.toggle_lazy_mode, name='toggle_lazy_mode'),
    path('today-share/', views.today_share_card, name='today_share_card'),
    path('execute/', views.daily_execute, name='daily_execute'),
    path('<int:pk>/publish/', views.publish_as_pattern, name='publish_as_pattern'),
]