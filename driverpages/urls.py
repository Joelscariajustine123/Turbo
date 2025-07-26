from django.urls import path
from . import views

app_name='driverpages'
urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('earnings/', views.earnings, name='earnings'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('ride/accept/<int:ride_id>/', views.accept_ride, name='accept_ride'),
    path('ride/decline/<int:ride_id>/', views.decline_ride, name='decline_ride'),
    # path('my-rides/', views.ride_history, name='ride_history'),
    path('ride/complete/<int:ride_id>/', views.complete_ride, name='complete_ride')
]
