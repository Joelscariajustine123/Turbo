from django.urls import path
from . import views

app_name='driverpages'
urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('earnings/', views.earnings, name='earnings'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
]
