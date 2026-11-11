from django.urls import path

from . import views

app_name = 'riderpages'

urlpatterns = [
    path('', views.index, name='index'),
    path('safety/', views.safety, name='safety'),
    path('outstation/', views.outstation, name='outstation'),
    path('contact/', views.contact, name='contact'),
    path('services/', views.services_page, name='services'),
    path('map/', views.map_view, name='map_view'),
    path('booking/<int:ride_id>/', views.booking_confirmation, name='booking_confirmation'),
    path('my-rides/', views.my_rides, name='my_rides'),
    path('my-rides/<int:ride_id>/cancel/', views.cancel_ride, name='cancel_ride'),
    path('track/<int:ride_id>/', views.track_ride, name='track_ride'),
]
