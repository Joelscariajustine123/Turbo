
from django.urls import path
from .views import *
app_name = 'account'
urlpatterns = [
    path('',first,name='usertype'),
    path('riderlogin/',riderlogin,name='rider_login'),
    path('driverlogin/',driverlogin,name='driver_login'),
    path('adminlogin/',adminlogin,name='admin_login'),
    path('adminsignup/',adminsignup,name='admin_signup'),
    path('driversignup/',driversignup,name='driver_signup'),
    path('ridersignup/',ridersignup,name='rider_signup'),
]