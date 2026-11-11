"""REST API for the React frontend and the Flutter apps.

All business rules live in the *services* modules of each app; these views only
translate HTTP <-> service calls, so the website and the API always behave the same.
"""
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from account import email_otp
from account.models import CustomUser
from account.services import register_user
from adminpages import services as admin_services
from driverpages import services as driver_services
from driverpages.models import AvailabilityStatus, DriverProfile, Earning
from riderpages import services as ride_services
from riderpages.models import (ACTIVE_STATUSES, BASE_FARE, CAR_CHOICES, PAYMENT_METHOD_CHOICES, RATE_PER_KM,
                               STATUS_CHOICES, ContactMessage, Ride)
from riderpages.pricing import all_fares

from . import serializers as s
from .permissions import IsAdminRole, IsDriver, IsRider


def _email_challenge(user, status_code=status.HTTP_200_OK):
    """Email a code and tell the client to collect it (no tokens yet)."""
    purpose = email_otp.purpose_for(user)
    email_otp.send_code(user, purpose)
    return Response({
        'otp_required': True,
        'challenge': email_otp.make_challenge(user, purpose),
        'purpose': purpose,
        'email': email_otp.mask_email(user.email),
        'detail': f"We sent a 6-digit code to {email_otp.mask_email(user.email)}.",
    }, status=status_code)


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    return {'access': str(refresh.access_token), 'refresh': str(refresh), 'user': s.UserSerializer(user).data}


def _rides():
    return Ride.objects.select_related('user', 'driver__user').prefetch_related('rating_set')


# ---------------------------------------------------------------- public / auth

class MetaView(APIView):
    """Static data the apps need: vehicle types and rates, statuses, UPI ID."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'base_fare': BASE_FARE,
            'car_types': [{'value': v, 'label': l, 'rate_per_km': RATE_PER_KM[v]} for v, l in CAR_CHOICES],
            'ride_statuses': [{'value': v, 'label': l} for v, l in STATUS_CHOICES],
            'payment_methods': [{'value': v, 'label': l} for v, l in PAYMENT_METHOD_CHOICES],
            'availability_statuses': [{'value': v, 'label': l} for v, l in AvailabilityStatus.choices],
            'upi_id': settings.UPI_ID,
        })


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        ser = s.RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = register_user(**ser.validated_data)
        if email_otp.enabled():
            return _email_challenge(user, status.HTTP_201_CREATED)
        return Response(_tokens_for(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST {email, password, role?} -> {access, refresh, user}.

    Pass `role` from each app so e.g. a rider can't sign in to the driver app.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        ser = s.LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        user = authenticate(request, email=data['email'], password=data['password'])
        if user is None or (data.get('role') and user.role != data['role']):
            return Response({'detail': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)
        if email_otp.enabled():
            return _email_challenge(user)
        return Response(_tokens_for(user))


class VerifyEmailOTPView(APIView):
    """POST {challenge, code} -> {access, refresh, user}. Finishes register or login."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        user, purpose = email_otp.read_challenge(request.data.get('challenge'))
        email_otp.verify_code(user, purpose, request.data.get('code'))
        user.refresh_from_db()
        return Response(_tokens_for(user))


class ResendEmailOTPView(APIView):
    """POST {challenge} -> a new code is emailed (max once a minute)."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        user, purpose = email_otp.read_challenge(request.data.get('challenge'))
        email_otp.send_code(user, purpose)
        return Response({'detail': f"A new code was sent to {email_otp.mask_email(user.email)}.",
                         'email': email_otp.mask_email(user.email)})


class LogoutView(APIView):
    """POST {refresh} — revokes the refresh token."""

    def post(self, request):
        try:
            RefreshToken(request.data.get('refresh', '')).blacklist()
        except TokenError:
            pass  # already invalid: logging out is still a success
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(s.UserSerializer(request.user).data)

    def patch(self, request):
        ser = s.UserSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        old_email = request.user.email
        user = ser.save()
        if user.email != old_email:
            # A new address must be confirmed (by code) at the next login.
            CustomUser.objects.filter(pk=user.pk).update(email_verified=False)
            user.email_verified = False
        return Response(s.UserSerializer(user).data)


class ChangePasswordView(APIView):
    def post(self, request):
        ser = s.ChangePasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(ser.validated_data['old_password']):
            return Response({'detail': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
        validate_password(ser.validated_data['new_password'], user=user)
        user.set_password(ser.validated_data['new_password'])
        user.save(update_fields=['password'])
        return Response({'detail': 'Password changed.'})


class ContactView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        msg = ride_services.save_contact_message(
            request.data.get('name'), request.data.get('email'), request.data.get('message'))
        return Response(s.ContactMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------- rider

class QuoteView(APIView):
    """POST pickup/drop coordinates -> road distance, route line and fare for every vehicle type."""
    permission_classes = [IsRider]

    def post(self, request):
        ser = s.QuoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        route = ride_services.quote(**ser.validated_data)
        return Response({
            'distance_km': route.distance_km,
            'source': route.source,
            'geometry': route.geometry,
            'fares': all_fares(route.distance_km),
        })


class RiderRideViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """/api/rider/rides/ — the logged-in rider's own rides."""
    permission_classes = [IsRider]
    serializer_class = s.RideSerializer

    def get_queryset(self):
        qs = _rides().filter(user=self.request.user)
        state = self.request.query_params.get('state')
        if state == 'active':
            qs = qs.filter(status__in=ACTIVE_STATUSES)
        elif state == 'past':
            qs = qs.filter(status__in=['COMPLETED', 'CANCELLED'])
        return qs

    def create(self, request):
        ser = s.RideCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ride = ride_services.create_ride(request.user, **ser.validated_data)
        return Response(self.get_serializer(self.get_queryset().get(pk=ride.pk)).data,
                        status=status.HTTP_201_CREATED)

    def _respond(self, ride):
        return Response(self.get_serializer(self.get_queryset().get(pk=ride.pk)).data)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        ser = s.PaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ride = ride_services.confirm_payment(self.get_object(), **ser.validated_data)
        return self._respond(ride)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return self._respond(ride_services.cancel_ride(self.get_object()))

    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        ser = s.RatingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ride = self.get_object()
        ride_services.rate_ride(ride, **ser.validated_data)
        return self._respond(ride)


# ---------------------------------------------------------------- driver

class DriverProfileView(APIView):
    """GET / PATCH the driver's profile. PATCH accepts JSON or multipart (for profile_photo)."""
    permission_classes = [IsDriver]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    FIELDS = ('full_name', 'phone', 'email', 'license_number', 'vehicle_info', 'vehicle_number',
              'vehicle_type', 'availability_status')

    def get(self, request):
        driver = driver_services.get_driver(request.user)
        return Response(s.DriverProfileSerializer(driver, context={'request': request}).data)

    def patch(self, request):
        driver = driver_services.get_driver(request.user)
        data = {k: request.data[k] for k in self.FIELDS if k in request.data}
        driver_services.update_profile(driver, data, photo=request.FILES.get('profile_photo'))
        driver.refresh_from_db()
        return Response(s.DriverProfileSerializer(driver, context={'request': request}).data)


class DriverRideViewSet(viewsets.GenericViewSet):
    """/api/driver/rides/available|ongoing|history/ and /{id}/accept|decline|complete/."""
    permission_classes = [IsDriver]
    serializer_class = s.RideSerializer
    queryset = Ride.objects.none()

    def _driver(self):
        return driver_services.get_driver(self.request.user)

    def _list(self, qs, **ctx):
        page = self.paginate_queryset(qs.prefetch_related('rating_set').select_related('driver__user'))
        ser = s.RideSerializer(page, many=True, context={'request': self.request, **ctx})
        return self.get_paginated_response(ser.data)

    def _one(self, ride_id):
        ride = _rides().get(pk=ride_id)
        return Response(s.RideSerializer(ride, context={'request': self.request}).data)

    @action(detail=False)
    def available(self, request):
        return self._list(driver_services.available_rides(self._driver()), hide_contact=True)

    @action(detail=False)
    def ongoing(self, request):
        return self._list(driver_services.ongoing_rides(self._driver()))

    @action(detail=False)
    def history(self, request):
        return self._list(driver_services.ride_history(self._driver()))

    @action(detail=False)
    def unpaid(self, request):
        """Completed rides still waiting for payment (e.g. cash to collect)."""
        return self._list(driver_services.unpaid_rides(self._driver()))

    @action(detail=True, methods=['post'], url_path='cash-collected')
    def cash_collected(self, request, pk=None):
        ride = driver_services.collect_cash(self._driver(), int(pk))
        return self._one(ride.pk)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        ride = driver_services.accept_ride(self._driver(), int(pk))
        return self._one(ride.pk)

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        driver_services.decline_ride(self._driver(), int(pk))
        return Response({'detail': 'Ride declined.'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        ride = driver_services.complete_ride(self._driver(), int(pk))
        return self._one(ride.pk)


class DriverEarningsView(APIView):
    permission_classes = [IsDriver]

    def get(self, request):
        driver = driver_services.get_driver(request.user)
        summary = driver_services.earnings_summary(driver)
        recent = (Earning.objects.filter(driver=driver).select_related('ride__user')
                  .order_by('-date', '-id')[:20])
        summary['recent'] = s.EarningSerializer(recent, many=True).data
        return Response(summary)


# ---------------------------------------------------------------- admin

class AdminStatsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        stats = admin_services.dashboard_stats()
        recent = _rides()[:5]
        stats['recent_rides'] = s.RideSerializer(recent, many=True,
                                                 context={'request': request, 'show_all': True}).data
        return Response(stats)


class AdminReportsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(list(admin_services.daily_reports()[:90]))


class AdminRideViewSet(viewsets.ReadOnlyModelViewSet):
    """/api/admin/rides/?status=COMPLETED&search=kannur  and  /api/admin/rides/payments/"""
    permission_classes = [IsAdminRole]
    serializer_class = s.RideSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'show_all': True}

    def get_queryset(self):
        qs = _rides()
        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status=params['status'].upper())
        if params.get('search'):
            q = params['search']
            qs = qs.filter(Q(pickup_location__icontains=q) | Q(drop_location__icontains=q) |
                           Q(user__full_name__icontains=q) | Q(driver__user__full_name__icontains=q))
        return qs

    @action(detail=False)
    def payments(self, request):
        qs = self.get_queryset().filter(payment_method__isnull=False)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class AdminRiderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                        mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = s.AdminUserSerializer

    def get_queryset(self):
        qs = CustomUser.objects.filter(role='rider').order_by('-date_joined')
        q = self.request.query_params.get('search')
        if q:
            qs = qs.filter(Q(full_name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
        return qs


class AdminDriverViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin,
                         viewsets.GenericViewSet):
    """Drivers are addressed by their *user* id. PATCH can change availability or is_active."""
    permission_classes = [IsAdminRole]
    serializer_class = s.DriverProfileSerializer
    lookup_field = 'user_id'
    lookup_url_kwarg = 'pk'

    def get_queryset(self):
        qs = DriverProfile.objects.select_related('user').order_by('-user__date_joined')
        q = self.request.query_params.get('search')
        if q:
            qs = qs.filter(Q(user__full_name__icontains=q) | Q(user__email__icontains=q) |
                           Q(vehicle_info__icontains=q) | Q(license_number__icontains=q))
        return qs

    def partial_update(self, request, pk=None):
        driver = self.get_object()
        if 'is_active' in request.data:
            driver.user.is_active = str(request.data['is_active']).lower() in ('true', '1')
            driver.user.save(update_fields=['is_active'])
        data = {k: request.data[k] for k in DriverProfileView.FIELDS if k in request.data}
        if data:
            driver_services.update_profile(driver, data)
        driver.refresh_from_db()
        return Response(self.get_serializer(driver).data)

    def perform_destroy(self, instance):
        instance.user.delete()  # deleting the account removes the profile too


class AdminMessageViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = s.ContactMessageSerializer
    queryset = ContactMessage.objects.all()


class AdminCreateAdminView(APIView):
    """Admins create other admins (public admin signup is closed once one exists)."""
    permission_classes = [IsAdminRole]

    def post(self, request):
        data = request.data
        user = register_user(role='admin', full_name=data.get('full_name'), username=data.get('username'),
                             email=data.get('email'), password=data.get('password', ''),
                             phone=data.get('phone', ''))
        return Response(s.UserSerializer(user).data, status=status.HTTP_201_CREATED)
