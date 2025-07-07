from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Index page
    path('dashboard/', views.dashboard, name='dashboard'),
    path('booking/', views.booking, name='booking'),
    path('payment/', views.payment, name='payment'),
    path('report/', views.report, name='report'),
    path('rider/', views.rider, name='rider'),
    path('settings/', views.settings, name='settings'),
]