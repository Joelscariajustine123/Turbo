from django.urls import path
from . import views

app_name = 'adminpages'

urlpatterns = [
    path('', views.home, name='home'),  # Index page
    path('dashboard/', views.dashboard, name='dashboard'),
    path('booking/', views.booking, name='booking'),
    path('payment/', views.payment, name='payment'),
    path('report/', views.report, name='report'),
    path('rider/', views.rider, name='rider'),
    path('settings/', views.settings, name='settings'),
    path('delete-rider/<int:rider_id>/', views.delete_rider, name='delete_rider'),
    path('edit-rider/<int:rider_id>/', views.edit_rider, name='edit_rider'),
]