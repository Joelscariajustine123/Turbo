# riderpages/urls.py

from django.urls import path
from .views import * # Imports all views from views.py

app_name = 'riderpages'

urlpatterns = [
    path('', index, name='index'),
    path('safety/', safety, name='safety'),
    path('outstation/', outstation, name='outstation'),
    path('contact/', contact, name='contact'),
    path('services/', services, name='services'),
    path('map/', map_view, name='map_view'), # URL for the booking map page
]