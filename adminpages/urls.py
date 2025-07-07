from django.urls import path
from .views import *

urlpatterns = [
    path('',home,name='admin_home'),
]