from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import tracking_views as tv
from . import views

router = DefaultRouter(trailing_slash=True)
router.register('rider/rides', views.RiderRideViewSet, basename='rider-ride')
router.register('driver/rides', views.DriverRideViewSet, basename='driver-ride')
router.register('admin/rides', views.AdminRideViewSet, basename='admin-ride')
router.register('admin/riders', views.AdminRiderViewSet, basename='admin-rider')
router.register('admin/drivers', views.AdminDriverViewSet, basename='admin-driver')
router.register('admin/messages', views.AdminMessageViewSet, basename='admin-message')

app_name = 'api'
urlpatterns = [
    path('meta/', views.MetaView.as_view(), name='meta'),
    path('contact/', views.ContactView.as_view(), name='contact'),

    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('auth/change-password/', views.ChangePasswordView.as_view(), name='change-password'),

    path('rider/quote/', views.QuoteView.as_view(), name='quote'),

    # Live tracking + pickup OTP
    path('driver/location/update/', tv.DriverLocationUpdateView.as_view(), name='driver-location-update'),
    path('driver/location/current/', tv.DriverCurrentLocationView.as_view(), name='driver-location-current'),
    path('driver/active-ride/', tv.DriverActiveRideView.as_view(), name='driver-active-ride'),
    path('driver/ride/status/', tv.DriverRideStatusView.as_view(), name='driver-ride-status'),
    path('driver/ride/verify-otp/', tv.DriverVerifyOTPView.as_view(), name='driver-verify-otp'),
    path('rider/ride/active/', tv.RiderActiveRideView.as_view(), name='rider-active-ride'),
    path('rider/ride/driver-location/', tv.RiderDriverLocationView.as_view(), name='rider-driver-location'),
    path('rider/ride/tracking/', tv.RiderTrackingView.as_view(), name='rider-tracking'),
    path('rider/ride/otp/', tv.RiderOTPView.as_view(), name='rider-otp'),
    path('rider/ride/otp/regenerate/', tv.RiderOTPRegenerateView.as_view(), name='rider-otp-regenerate'),

    path('driver/profile/', views.DriverProfileView.as_view(), name='driver-profile'),
    path('driver/earnings/', views.DriverEarningsView.as_view(), name='driver-earnings'),

    path('admin/stats/', views.AdminStatsView.as_view(), name='admin-stats'),
    path('admin/reports/', views.AdminReportsView.as_view(), name='admin-reports'),
    path('admin/admins/', views.AdminCreateAdminView.as_view(), name='admin-create-admin'),

    path('', include(router.urls)),
]
