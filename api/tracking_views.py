"""Live tracking + pickup OTP endpoints.

Access rules (all enforced here, server-side):
* Riders only ever see their own ride, and the driver's location only while that
  ride is in a trip status (ACCEPTED, ARRIVED, IN_PROGRESS).
* Drivers only act on rides assigned to them; the OTP is never sent to a driver.
* Ride status changes go through driverpages.services, which allows only valid
  transitions (IN_PROGRESS is reachable only with a correct OTP).
"""
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from driverpages import services as driver_services
from driverpages import tracking
from driverpages.models import DriverLocation
from riderpages import otp as otp_service
from riderpages.models import ACTIVE_STATUSES, TRIP_STATUSES, Ride

from . import serializers as s
from .permissions import IsDriver, IsRider


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')) or None


def _ride_json(request, ride):
    return s.RideSerializer(ride, context={'request': request}).data


def _photo_url(request, details):
    if details and details.get('photo'):
        details = {**details, 'photo': request.build_absolute_uri(details['photo'])}
    return details


def _driver_card(request, ride):
    if ride.driver_id is None:
        return None
    key = f'turbo:drivercard:{ride.driver_id}'
    card = cache.get(key)
    if card is None:
        card = tracking.driver_details(ride.driver)
        cache.set(key, card, 60)
    return _photo_url(request, card)


def driver_active_ride_data(request, driver):
    """Shared by the API and the driver's live-map page (initial render)."""
    ride = tracking.active_trip_for_driver(driver)
    if ride is None:
        return {'ride': None, 'rider': None, 'tracking': None, 'driver_status': tracking.driver_status(driver)}
    return {
        'ride': _ride_json(request, ride),
        'rider': {'full_name': ride.user.full_name, 'phone': ride.user.phone},
        'tracking': tracking.trip_payload(ride),
        'driver_status': tracking.driver_status(driver, ride),
    }


def rider_tracking_data(request, ride):
    """Shared by the API and the rider's tracking page (initial render)."""
    data = tracking.trip_payload(ride)
    data['driver'] = _driver_card(request, ride) if ride.status in TRIP_STATUSES else None
    data['fare'] = float(ride.fare) if ride.fare is not None else None
    data['car_type_display'] = ride.get_car_type_display()
    data['payment_method_display'] = ride.get_payment_method_display()
    data['rating'] = next((r.rating for r in ride.rating_set.all()), None)
    return data


# ---------------------------------------------------------------- driver

class _DriverView(APIView):
    permission_classes = [IsDriver]

    def driver(self):
        return driver_services.get_driver(self.request.user)


class DriverLocationUpdateView(_DriverView):
    """POST {latitude, longitude, accuracy?, speed?, heading?} every ~3 s while online.

    Returns the driver's status and, during a trip, the same tracking data the rider sees.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'location'

    def post(self, request):
        ser = s.LocationUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        driver = self.driver()
        try:
            loc, ride = tracking.update_location(driver, **ser.validated_data)
        except ValidationError as exc:
            # 409: the client should stop sending (e.g. the driver is offline).
            return Response({'detail': exc.messages[0], 'tracking_allowed': False}, status=status.HTTP_409_CONFLICT)
        return Response({
            'location': tracking.location_payload(loc),
            'driver_status': tracking.driver_status(driver, ride),
            'tracking': tracking.trip_payload(ride, loc) if ride else None,
        })


class DriverCurrentLocationView(_DriverView):
    def get(self, request):
        driver = self.driver()
        loc = DriverLocation.objects.filter(driver=driver).first()
        return Response({
            'location': tracking.location_payload(loc),
            'driver_status': tracking.driver_status(driver, tracking.active_trip_for_driver(driver)),
            'availability_status': driver.availability_status,
        })


class DriverActiveRideView(_DriverView):
    def get(self, request):
        return Response(driver_active_ride_data(request, self.driver()))


class DriverRideStatusView(_DriverView):
    """POST {ride_id, status}: ARRIVED or COMPLETED. IN_PROGRESS needs verify-otp."""

    def post(self, request):
        ser = s.RideStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ride = driver_services.change_ride_status(self.driver(), **ser.validated_data)
        ride = Ride.objects.select_related('user', 'driver__user').get(pk=ride.pk)
        return Response({'ride': _ride_json(request, ride), 'tracking': tracking.trip_payload(ride)})


class DriverVerifyOTPView(_DriverView):
    """POST {ride_id, otp}. 5 wrong attempts lock verification; every attempt is logged."""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp'

    def post(self, request):
        ser = s.VerifyOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            ride = driver_services.verify_pickup_otp(
                self.driver(), ser.validated_data['ride_id'], ser.validated_data['otp'].strip(), _client_ip(request))
        except ValidationError as exc:
            return Response({
                'detail': exc.messages[0],
                'code': getattr(exc, 'code', None) or 'invalid',
                'attempts_left': getattr(exc, 'attempts_left', None),
            }, status=status.HTTP_400_BAD_REQUEST)
        ride = Ride.objects.select_related('user', 'driver__user').get(pk=ride.pk)
        return Response({'detail': 'Passenger verified. Ride started.', 'ride': _ride_json(request, ride),
                         'tracking': tracking.trip_payload(ride)})


# ---------------------------------------------------------------- rider

class _RiderRideView(APIView):
    """Resolves ?ride_id= (must be the rider's own) or the rider's latest active ride."""
    permission_classes = [IsRider]

    def get_ride(self, required=True):
        qs = Ride.objects.select_related('user', 'driver__user').filter(user=self.request.user)
        ride_id = self.request.query_params.get('ride_id')
        if not ride_id and self.request.method == 'POST':
            ride_id = self.request.data.get('ride_id')
        if ride_id:
            if not str(ride_id).isdigit():
                raise NotFound("Ride not found.")
            return get_object_or_404(qs, pk=ride_id)
        ride = qs.filter(status__in=ACTIVE_STATUSES).order_by('-created_at').first()
        if ride is None and required:
            raise NotFound("You have no active ride.")
        return ride


class RiderActiveRideView(_RiderRideView):
    def get(self, request):
        ride = self.get_ride(required=False)
        if ride is None:
            return Response({'ride': None, 'driver': None, 'tracking': None})
        return Response({
            'ride': _ride_json(request, ride),
            'driver': _driver_card(request, ride) if ride.status in TRIP_STATUSES else None,
            'tracking': tracking.trip_payload(ride),
        })


class RiderDriverLocationView(_RiderRideView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'tracking'

    def get(self, request):
        ride = self.get_ride()
        if ride.status not in TRIP_STATUSES or ride.driver_id is None:
            return Response({'detail': "The driver's location is shared only during your active trip."},
                            status=status.HTTP_404_NOT_FOUND)
        loc = DriverLocation.objects.filter(driver_id=ride.driver_id, is_online=True).first()
        return Response({'ride_id': ride.pk, 'status': ride.status,
                         'location': tracking.location_payload(loc)})


class RiderTrackingView(_RiderRideView):
    """Everything the rider's live map needs, in one request (poll every ~3 s)."""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'tracking'

    def get(self, request):
        return Response(rider_tracking_data(request, self.get_ride()))


class RiderOTPView(_RiderRideView):
    """GET: the pickup code for the rider's own ride (only before the ride starts)."""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'tracking'

    def get(self, request):
        ride = self.get_ride()
        if ride.status not in ('ACCEPTED', 'ARRIVED') or ride.otp_verified:
            return Response({'detail': 'No pickup code is needed for this ride right now.', 'ride_id': ride.pk,
                             'status': ride.status}, status=status.HTTP_404_NOT_FOUND)
        view = otp_service.for_rider(ride)
        if view is None:  # e.g. a ride accepted before OTPs existed
            otp_service.issue(ride)
            view = otp_service.for_rider(ride)
        return Response({'ride_id': ride.pk, 'status': ride.status, **view.as_dict()})


class RiderOTPRegenerateView(_RiderRideView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp'

    def post(self, request):
        ride = self.get_ride()
        otp_service.regenerate(ride)
        view = otp_service.for_rider(ride)
        return Response({'ride_id': ride.pk, 'status': ride.status, **view.as_dict()})
