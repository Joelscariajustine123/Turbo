"""Distance and fare calculation, done on the server so clients can't set the price.

Road distance comes from an OSRM routing server (settings.ROUTING_URL). If that is
switched off or unreachable, it falls back to straight-line distance x ROAD_FACTOR.
"""
import json
import logging
import math
import urllib.request
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError

from .models import BASE_FARE, RATE_PER_KM

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal('0.01')
ROAD_FACTOR = 1.3          # typical road distance vs straight line
MAX_DISTANCE_KM = 2000
OSRM_DOWN_KEY = 'turbo:osrm-down'
OSRM_BACKOFF_SECONDS = 300  # after a failure, use the estimate for 5 minutes


AVERAGE_SPEED_KMH = 25     # used for ETAs when the routing server gives no duration


@dataclass
class Route:
    distance_km: Decimal
    geometry: list = field(default_factory=list)   # [[lat, lng], ...] for drawing on a map
    source: str = 'estimate'                       # 'osrm' or 'estimate'
    duration_min: float = 0.0                      # expected driving time


def parse_point(lat, lng, label):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} location is missing. Choose it on the map.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValidationError(f"{label} location has invalid coordinates.")
    return lat, lng


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _osrm_route(lat1, lng1, lat2, lng2):
    base = getattr(settings, 'ROUTING_URL', '')
    if not base or cache.get(OSRM_DOWN_KEY):
        return None
    url = (f"{base.rstrip('/')}/route/v1/driving/{lng1},{lat1};{lng2},{lat2}"
           "?overview=simplified&geometries=geojson")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'TurboCab/1.0'})
        with urllib.request.urlopen(req, timeout=getattr(settings, 'ROUTING_TIMEOUT', 5)) as resp:
            data = json.load(resp)
        route = data['routes'][0]
        coords = [[lat, lng] for lng, lat in route['geometry']['coordinates']]
        return route['distance'] / 1000.0, coords, route.get('duration', 0) / 60.0
    except Exception as exc:  # network error, bad response, no route...
        logger.warning("OSRM routing failed, using estimates for %ss: %s", OSRM_BACKOFF_SECONDS, exc)
        cache.set(OSRM_DOWN_KEY, True, OSRM_BACKOFF_SECONDS)
        return None


def route_between(lat1, lng1, lat2, lng2):
    """Road route between two points, without booking validation (used by live tracking)."""
    osrm = _osrm_route(lat1, lng1, lat2, lng2)
    if osrm:
        km, geometry, minutes, source = osrm[0], osrm[1], osrm[2], 'osrm'
    else:
        km = haversine_km(lat1, lng1, lat2, lng2) * ROAD_FACTOR
        geometry, source = [[lat1, lng1], [lat2, lng2]], 'estimate'
        minutes = 0
    if not minutes:
        minutes = km / AVERAGE_SPEED_KMH * 60
    km = Decimal(str(km)).quantize(TWO_PLACES, ROUND_HALF_UP)
    return Route(distance_km=km, geometry=geometry, source=source, duration_min=round(minutes, 1))


def get_route(lat1, lng1, lat2, lng2):
    """Route for booking a ride: rejects zero-length and overly long trips."""
    route = route_between(lat1, lng1, lat2, lng2)
    km = route.distance_km
    if km <= 0:
        raise ValidationError("Pickup and drop are the same place.")
    if km > MAX_DISTANCE_KM:
        raise ValidationError("That trip is too long to book.")
    return route


def calculate_fare(car_type, distance_km):
    if car_type not in RATE_PER_KM:
        raise ValidationError("Please select a valid vehicle type.")
    fare = Decimal(BASE_FARE) + Decimal(distance_km) * RATE_PER_KM[car_type]
    return fare.quantize(TWO_PLACES, ROUND_HALF_UP)


def all_fares(distance_km):
    return {car: calculate_fare(car, distance_km) for car in RATE_PER_KM}
