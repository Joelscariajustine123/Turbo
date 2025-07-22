from django.urls import path
from .views import *
app_name = 'riderpages'
urlpatterns = [
    path('',index,name='index'),
    path('safety/',safety,name='safety'),
    path('outstation/',outstation,name='outstation'),
    path('contact/',contact,name='contact'),
    path('services/',services,name='services'),
]