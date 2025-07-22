from django.urls import path
from .views import *
app_name = 'riderpages'
urlpatterns = [
    path('',index,name='index'),
]