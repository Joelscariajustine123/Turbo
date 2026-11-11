"""Live driver location + trip tracking shared by the driver and rider screens.

Writes are kept small: one DriverLocation row per driver is overwritten on each
GPS update (every ~3 s), and a sparse TripLocationPoint breadcrumb is stored at
most every HISTORY_EVERY seconds / HISTORY_MIN_METRES during an active ride.

Routes come from riderpages.pricing (OSRM, falling back to a straight-line
estimate). They are cached per ride and stage and only recalculated when the
driver leaves the route, the stage changes, or the cache gets old — never on
every GPS update. Remaining distance and ETA are measured along the cached route.
"""
import math
import time
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Avg
from django.utils import timezone

from riderpages.models import TRIP_STATUSES, Ride
from riderpages.pricing import haversine_km, route_between

from .models import AvailabilityStatus, DriverLocation, TripLocationPoint

STALE_AFTER = timedelta(seconds=20)       # rider sees "GPS signal lost" after this
HISTORY_EVERY = 15                        # seconds between breadcrumb points
HISTORY_MIN_METRES = 30
OFF_ROUTE_KM = 0.25                       # recalculate the route if the driver strays this far
ROUTE_MAX_AGE = 300                       # seconds; refresh traffic-free routes periodically
ARRIVAL_RADIUS_KM = 0.15                  # "you're at the pickup" hint for the driver

DRIVER_STATUS_LABELS = {
    'offline': 'Offline',
    'online': 'Online',
    'ACCEPTED': 'On the way to pickup',
    'ARRIVED': 'Arrived at pickup',
    'IN_PROGRESS': 'On the way to destination',
    'COMPLETED': 'Completed',
}

RIDE_STAGE_LABELS = {
    'PENDING': 'Booking created · awaiting payment',
    'CONFIRMED': 'Booking confirmed · finding a driver',
    'ACCEPTED': 'Driver assigned · on the way to pickup',
    'ARRIVED': 'Driver arrived · share your OTP',
    'IN_PROGRESS': 'Ride started · on the way to destination',
    'COMPLETED': 'Ride completed',
    'CANCELLED': 'Ride cancelled',
}


# ---------------------------------------------------------------- helpers

def _f(v):
    return float(v) if v is not None else None


def _point(lat, lng):
    return {'lat': _f(lat), 'lng': _f(lng)} if lat is not None and lng is not None else None


def active_trip_for_driver(driver):
    return (Ride.objects.select_related('user', 'driver__user')
            .filter(driver=driver, status__in=TRIP_STATUSES)
            .order_by('-accepted_at', '-created_at').first())


def validate_coordinates(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise ValidationError("Latitude and longitude must be numbers.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
        raise ValidationError("Invalid GPS coordinates.")
    return lat, lng


# ---------------------------------------------------------------- driver side

def update_location(driver, latitude, longitude, accuracy=None, speed=None, heading=None):
    """Save the driver's latest GPS fix. Only allowed while the driver is online."""
    if driver.availability_status == AvailabilityStatus.OFFLINE:
        raise ValidationError("You are offline. Go online to share your location.")
    lat, lng = validate_coordinates(latitude, longitude)
    ride = active_trip_for_driver(driver)
    values = {
        'latitude': Decimal(f'{lat:.6f}'), 'longitude': Decimal(f'{lng:.6f}'),
        'accuracy': accuracy, 'speed': speed, 'heading': heading,
        'is_online': True, 'ride': ride, 'updated_at': timezone.now(),
    }
    # One UPDATE per fix; INSERT only the very first time.
    if not DriverLocation.objects.filter(driver=driver).update(**values):
        values.pop('updated_at')
        DriverLocation.objects.create(driver=driver, **values)
    if ride is not None:
        _record_breadcrumb(ride, lat, lng, speed, heading)
    return DriverLocation.objects.get(driver=driver), ride


def _record_breadcrumb(ride, lat, lng, speed, heading):
    key = f'turbo:crumb:{ride.pk}'
    last = cache.get(key)
    now = time.time()
    if last and now - last[2] < HISTORY_EVERY and haversine_km(last[0], last[1], lat, lng) * 1000 < HISTORY_MIN_METRES:
        return
    TripLocationPoint.objects.create(ride=ride, latitude=Decimal(f'{lat:.6f}'), longitude=Decimal(f'{lng:.6f}'),
                                     speed=speed, heading=heading)
    cache.set(key, (lat, lng, now), 3600)


def stop_sharing(driver):
    """Driver went offline: stop exposing their position."""
    DriverLocation.objects.filter(driver=driver).update(is_online=False, ride=None)


def purge_history(days=None):
    days = days if days is not None else getattr(settings, 'TURBO_TRACK_RETENTION_DAYS', 30)
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = TripLocationPoint.objects.filter(recorded_at__lt=cutoff).delete()
    return deleted


def location_payload(loc):
    if loc is None:
        return None
    age = (timezone.now() - loc.updated_at).total_seconds()
    return {
        'lat': _f(loc.latitude), 'lng': _f(loc.longitude),
        'accuracy': loc.accuracy, 'speed': loc.speed, 'heading': loc.heading,
        'updated_at': loc.updated_at, 'age_seconds': round(age, 1),
        'is_stale': age > STALE_AFTER.total_seconds(), 'is_online': loc.is_online,
    }


def driver_status(driver, ride=None):
    if ride is not None and ride.status in TRIP_STATUSES:
        key = ride.status
    elif driver.availability_status == AvailabilityStatus.OFFLINE:
        key = 'offline'
    else:
        key = 'online'
    return {'key': key, 'label': DRIVER_STATUS_LABELS[key]}


# ---------------------------------------------------------------- routes

def _polyline_km(points, start=0):
    return sum(haversine_km(*points[i], *points[i + 1]) for i in range(start, len(points) - 1))


def _remaining_along(geometry, lat, lng):
    """Distance left along `geometry` from the point nearest to (lat, lng), and how far off-route we are."""
    best_i, best_d = 0, float('inf')
    for i, (plat, plng) in enumerate(geometry):
        d = haversine_km(lat, lng, plat, plng)
        if d < best_d:
            best_i, best_d = i, d
    return best_d + _polyline_km(geometry, best_i), best_d


def _cached_route(key, origin, target, max_age=ROUTE_MAX_AGE):
    cached = cache.get(key)
    if cached:
        remaining, off = _remaining_along(cached['geometry'], *origin)
        fresh = time.time() - cached['at'] < max_age
        if off <= OFF_ROUTE_KM and fresh:
            return cached, remaining
    route = route_between(*origin, *target)
    geometry = route.geometry if len(route.geometry) >= 2 else [list(origin), list(target)]
    cached = {
        'geometry': geometry, 'distance_km': float(route.distance_km),
        'duration_min': route.duration_min, 'source': route.source, 'at': time.time(),
    }
    cache.set(key, cached, 3600)
    return cached, float(route.distance_km)


def _eta_minutes(cached, remaining_km):
    if remaining_km <= 0.02:
        return 0
    if cached['distance_km'] > 0 and cached['duration_min'] > 0:
        speed = cached['distance_km'] / (cached['duration_min'] / 60)
    else:
        speed = 25
    speed = min(max(speed, 12), 60)  # keep ETAs sensible for city driving
    return max(1, math.ceil(remaining_km / speed * 60))


def trip_route(ride):
    """Pickup -> destination route (computed once per ride)."""
    if None in (ride.pickup_lat, ride.pickup_lng, ride.drop_lat, ride.drop_lng):
        return None
    key = f'turbo:triproute:{ride.pk}'
    cached = cache.get(key)
    if not cached:
        route = route_between(float(ride.pickup_lat), float(ride.pickup_lng), float(ride.drop_lat), float(ride.drop_lng))
        cached = {'geometry': route.geometry, 'distance_km': float(route.distance_km),
                  'duration_min': route.duration_min, 'source': route.source}
        cache.set(key, cached, 6 * 3600)
    return cached


# ---------------------------------------------------------------- shared tracking payload

def trip_payload(ride, loc=None):
    """Everything both maps need: points, live position, active route, distance, ETA."""
    if loc is None and ride.driver_id:
        loc = DriverLocation.objects.filter(driver_id=ride.driver_id).first()
    sharing = ride.status in TRIP_STATUSES and loc is not None and loc.is_online
    pickup = _point(ride.pickup_lat, ride.pickup_lng)
    drop = _point(ride.drop_lat, ride.drop_lng)
    stage = 'pickup' if ride.status in ('ACCEPTED', 'ARRIVED') else 'destination' if ride.status == 'IN_PROGRESS' else None

    payload = {
        'ride_id': ride.pk,
        'status': ride.status,
        'status_display': ride.get_status_display(),
        'stage': stage,
        'stage_label': RIDE_STAGE_LABELS.get(ride.status, ride.get_status_display()),
        'otp_verified': ride.otp_verified,
        'pickup': pickup and {**pickup, 'label': ride.pickup_location},
        'drop': drop and {**drop, 'label': ride.drop_location},
        'driver_location': location_payload(loc) if sharing else None,
        'tracking_active': sharing,
        'route': None,
        'trip_route': None,
        'distance_to_pickup_km': None,
        'distance_to_destination_km': None,
        'eta_minutes': None,
        'eta_at': None,
        'near_target': False,
        'timestamps': {k: getattr(ride, f'{k}_at') for k in ('accepted', 'arrived', 'started', 'completed')},
    }
    tr = trip_route(ride) if ride.status in TRIP_STATUSES else None
    if tr:
        payload['trip_route'] = {'geometry': tr['geometry'], 'distance_km': round(tr['distance_km'], 2)}

    if not sharing or stage is None:
        return payload

    here = (float(loc.latitude), float(loc.longitude))
    target = pickup if stage == 'pickup' else drop
    if target is None:
        return payload
    target_xy = (target['lat'], target['lng'])
    cached, remaining = _cached_route(f'turbo:route:{ride.pk}:{stage}', here, target_xy)
    if ride.status == 'ARRIVED':
        remaining = haversine_km(*here, *target_xy)
    eta = 0 if ride.status == 'ARRIVED' else _eta_minutes(cached, remaining)

    payload.update({
        'route': {'geometry': cached['geometry'], 'source': cached['source'], 'to': stage},
        'eta_minutes': eta,
        'eta_at': timezone.now() + timedelta(minutes=eta),
        'near_target': haversine_km(*here, *target_xy) <= ARRIVAL_RADIUS_KM,
    })
    if stage == 'pickup':
        payload['distance_to_pickup_km'] = round(remaining, 2)
        if tr:
            payload['distance_to_destination_km'] = round(remaining + tr['distance_km'], 2)
    else:
        payload['distance_to_destination_km'] = round(remaining, 2)
    return payload


def driver_details(driver):
    """Driver card shown to the rider of an assigned ride."""
    rating = driver.ratings.aggregate(avg=Avg('rating'))['avg']
    return {
        'id': driver.user_id,
        'full_name': driver.user.full_name,
        'phone': driver.user.phone,
        'photo': driver.profile_photo.url if driver.profile_photo else None,
        'vehicle_model': driver.vehicle_info,
        'vehicle_number': driver.vehicle_number,
        'vehicle_type': driver.get_vehicle_type_display() if driver.vehicle_type else '',
        'rating': round(rating, 1) if rating else None,
        'rating_count': driver.ratings.count(),
    }
