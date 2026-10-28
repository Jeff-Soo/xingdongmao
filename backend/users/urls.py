from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path('<int:pk>/', views.user_profile, name='user_profile'),
]
