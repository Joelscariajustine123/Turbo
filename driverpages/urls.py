from django.urls import path
from .views import *


urlpatterns = [
    path('', homepage, name='driver_homepage'),
    path('earnings/', earnings, name='driver_earnings'),
    path('profile/', profile, name='driver_profile'),
    path('settings/', setting, name='driver_settings'),
]


