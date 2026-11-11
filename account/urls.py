from django.urls import path

from . import views

app_name = 'account'
urlpatterns = [
    path('', views.first, name='usertype'),
    path('riderlogin/', views.riderlogin, name='rider_login'),
    path('driverlogin/', views.driverlogin, name='driver_login'),
    path('adminlogin/', views.adminlogin, name='admin_login'),
    path('adminsignup/', views.adminsignup, name='admin_signup'),
    path('driversignup/', views.driversignup, name='driver_signup'),
    path('ridersignup/', views.ridersignup, name='rider_signup'),
    path('logout/', views.logout_view, name='logout'),
]
