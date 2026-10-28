from django.urls import path
from . import tasks_views, views

app_name = 'api'

urlpatterns = [
    # 登录（固定路径，和下面的固定路径一样要放在 <int:pk> 之前）
    path('auth/wx-login/', views.wx_login, name='wx_login'),
    path('auth/dev-login/', views.dev_login, name='dev_login'),
    # 网页版邮箱密码（#027）
    path('auth/register/', views.auth_register, name='auth_register'),
    path('auth/login/', views.auth_login, name='auth_login'),
    # 忘记密码（#028）
    path('auth/forgot/', views.auth_forgot, name='auth_forgot'),
    path('auth/reset/', views.auth_reset, name='auth_reset'),
    path('quick/', views.quick_collection, name='quick_collection'),
    # 固定路径必须放在 <int:pk> 之前，否则会被当 pk 解析
    path('quick/my-notes/', views.quick_my_notes, name='quick_my_notes'),
    path('quick/my-favorites/', views.quick_my_favorites, name='quick_my_favorites'),
    path('quick/import/', views.quick_import, name='quick_import'),
    # #046 内部批量导入（仅 is_staff；普通用户 401/403，拿不到任何数据）
    path('quick/batch-import/', views.quick_batch_import, name='quick_batch_import'),
    path('quick/suggest/', views.quick_suggest, name='quick_suggest'),
    path('quick/me/', views.quick_me, name='quick_me'),
    # #071 浏览记录（我最近看过的公开模板）
    path('quick/history/', views.quick_history, name='quick_history'),
    path('quick/tags/', views.quick_tags, name='quick_tags'),
    # #072⑦ 多选合并（几个公开模板 → 一个新草稿，进编辑页）
    path('quick/merge/', views.quick_merge, name='quick_merge'),
    # #071 个人资料（昵称 / 头像）
    path('me/profile/', views.me_profile, name='me_profile'),
    path('me/avatar/', views.me_avatar, name='me_avatar'),
    path('quick/<int:pk>/', views.quick_detail, name='quick_detail'),
    path('quick/<int:pk>/execute/', views.quick_execute, name='quick_execute'),
    path('quick/<int:pk>/rate/', views.quick_rate, name='quick_rate'),
    path('quick/<int:pk>/note/', views.quick_note, name='quick_note'),
    path('quick/<int:pk>/notes/', views.quick_notes, name='quick_notes'),
    path('quick/<int:pk>/fork/', views.quick_fork, name='quick_fork'),
    path('quick/<int:pk>/favorite/', views.quick_favorite, name='quick_favorite'),
    path('quick/<int:pk>/unfavorite/', views.quick_unfavorite, name='quick_unfavorite'),
    path('quick/<int:pk>/publish/', views.quick_publish, name='quick_publish'),
    path('quick/<int:pk>/edit/', views.quick_edit, name='quick_edit'),
    path('quick/<int:pk>/delete/', views.quick_delete, name='quick_delete'),
    path('quick/<int:pk>/share/', views.quick_share_card, name='quick_share_card'),

    # ===== #079 日常任务（实现在 api/tasks_views.py）=====
    # 固定路径写在 <int:pk> 之前（"calendar"/"from-step" 不是数字，其实不会误吞，但保持一致）
    path('tasks/', tasks_views.task_collection, name='task_collection'),
    path('tasks/calendar/', tasks_views.task_calendar, name='task_calendar'),
    path('tasks/from-step/', tasks_views.task_from_step, name='task_from_step'),
    path('tasks/<int:pk>/', tasks_views.task_item, name='task_item'),
    # #080：加步骤用不带 sid 的同一段路径，按方法区分（POST=加；PATCH/DELETE=改/删某一步）
    path('tasks/<int:pk>/steps/', tasks_views.task_step_create, name='task_step_create'),
    path('tasks/<int:pk>/steps/<int:sid>/', tasks_views.task_step_toggle, name='task_step_toggle'),
]
