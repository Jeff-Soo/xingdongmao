# patterns/urls.py
from django.urls import path
from . import views

app_name = 'patterns'

urlpatterns = [
    path('create/', views.create_pattern, name='create_pattern'),
    path('<int:pk>/delete/', views.delete_pattern, name='delete_pattern'),
    path('<int:pk>/edit/', views.edit_pattern, name='edit_pattern'),
    path('', views.pattern_list, name='pattern_list'),
    path('<int:pk>/', views.pattern_detail, name='pattern_detail'),
    path('<int:pk>/share/', views.share_card, name='share_card'),
    path('<int:pk>/export/', views.export_pattern, name='export_pattern'),
]
