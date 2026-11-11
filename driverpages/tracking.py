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
HISTORY_EVERY = 5                         # seconds between breadcrumb points ...
HISTORY_MIN_METRES = 10                   # ... or this much movement
OFF_ROUTE_KM = 0.10                       # recalculate the route if the driver strays 100 m
ROUTE_MAX_AGE = 120                       # seconds; refresh routes regularly
BAD_FIX_ACCURACY_M = 150                  # ignore fixes worse than this while a good one is recent
GOOD_FIX_MAX_AGE = timedelta(seconds=20)
GEOFENCE_MAX_AGE = timedelta(seconds=30)  # "Arrived"/"Complete" need a fix at most this old ...
GEOFENCE_MAX_ACCURACY_M = 75              # ... and at least this precise


def geofence_radius_m():
    return getattr(settings, 'TURBO_GEOFENCE_RADIUS_M', 50)

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
    current = DriverLocation.objects.filter(driver=driver).first()
    if (accuracy is not None and accuracy > BAD_FIX_ACCURACY_M and current is not None and current.is_online
            and current.accuracy is not None and current.accuracy <= BAD_FIX_ACCURACY_M
            and timezone.now() - current.updated_at < GOOD_FIX_MAX_AGE):
        # A rough network fix right after a good GPS one: keep the precise position.
        return current, ride
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


def _project(lat, lng, a, b):
    """Project point P onto segment AB (local flat approximation, fine for <100 km).
    Returns (t along AB in 0..1, perpendicular distance in km)."""
    k = math.cos(math.radians(lat)) * 111.32
    px, py = lng * k, lat * 110.574
    ax, ay, bx, by = a[1] * k, a[0] * 110.574, b[1] * k, b[0] * 110.574
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    cx, cy = ax + t * dx, ay + t * dy
    return t, math.hypot(px - cx, py - cy)


def _remaining_along(geometry, lat, lng):
    """Distance still to drive along `geometry` from the driver's position projected onto
    the route, and how far the driver is from the route (km)."""
    if len(geometry) < 2:
        return haversine_km(lat, lng, *geometry[-1]), 0.0
    best = (0, 0.0, float('inf'))  # segment index, t, off-route distance
    for i in range(len(geometry) - 1):
        t, off = _project(lat, lng, geometry[i], geometry[i + 1])
        if off < best[2]:
            best = (i, t, off)
    i, t, off = best
    seg = haversine_km(*geometry[i], *geometry[i + 1])
    return seg * (1 - t) + _polyline_km(geometry, i + 1), off


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
    """Share of the route's expected driving time still ahead (OSRM durations per road type)."""
    if remaining_km <= 0.02:
        return 0
    if cached['distance_km'] > 0 and cached['duration_min'] > 0:
        minutes = cached['duration_min'] * min(1.0, remaining_km / cached['distance_km'])
        speed = remaining_km / (minutes / 60) if minutes else 25
        if not 8 <= speed <= 80:  # implausible (e.g. straight-line estimate): fall back to city speed
            minutes = remaining_km / 25 * 60
    else:
        minutes = remaining_km / 25 * 60
    return max(1, math.ceil(minutes))


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


# ---------------------------------------------------------------- geofence (50 m rule)

def _target_point(ride, kind):
    lat, lng = (ride.pickup_lat, ride.pickup_lng) if kind == 'pickup' else (ride.drop_lat, ride.drop_lng)
    return None if lat is None or lng is None else (float(lat), float(lng))


def geofence_status(ride, loc, kind):
    """How far the driver's latest fix is from the pickup/drop, and whether the 50 m rule is met."""
    target = _target_point(ride, kind)
    radius = geofence_radius_m()
    if target is None:
        return {'radius_m': radius, 'distance_m': None, 'within': True, 'reason': 'no_coordinates'}
    if loc is None or not loc.is_online:
        return {'radius_m': radius, 'distance_m': None, 'within': False, 'reason': 'no_gps'}
    distance_m = haversine_km(float(loc.latitude), float(loc.longitude), *target) * 1000
    fresh = timezone.now() - loc.updated_at <= GEOFENCE_MAX_AGE
    precise = loc.accuracy is None or loc.accuracy <= GEOFENCE_MAX_ACCURACY_M
    within = distance_m <= radius and fresh and precise
    reason = 'ok' if within else 'stale' if not fresh else 'imprecise' if not precise else 'too_far'
    return {'radius_m': radius, 'distance_m': round(distance_m), 'within': within, 'reason': reason,
            'accuracy_m': loc.accuracy}


def require_within(ride, kind):
    """Raise unless the driver's live position is within the radius of the pickup/drop."""
    loc = DriverLocation.objects.filter(driver_id=ride.driver_id).first()
    g = geofence_status(ride, loc, kind)
    if g['within']:
        return
    place = 'pickup point' if kind == 'pickup' else 'destination'
    action = '"Arrived"' if kind == 'pickup' else '"Complete ride"'
    messages = {
        'no_gps': f"We don't have your live location. Keep the app open with GPS on to use {action}.",
        'stale': f"Your last GPS update is too old. Wait for a fresh fix to use {action}.",
        'imprecise': f"Your GPS isn't precise enough (±{round(g.get('accuracy_m') or 0)} m). "
                     "Move to open sky and try again.",
        'too_far': f"You're {g['distance_m']} m from the {place}. {action} unlocks within {g['radius_m']} m.",
    }
    raise ValidationError(messages[g['reason']], code=g['reason'])


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
        'geofence': None,
        'payment_status': ride.payment_status,
        'payment_status_display': ride.get_payment_status_display(),
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
    })
    g = geofence_status(ride, loc, stage)
    payload['geofence'] = g
    payload['near_target'] = g['within']
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
