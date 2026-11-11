from django.conf import settings


def map_settings():
    """Settings for static/tracking/map.js (TurboMap.create)."""
    key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    return {'provider': 'google' if key else 'osm', 'googleKey': key,
            'mapId': getattr(settings, 'GOOGLE_MAPS_MAP_ID', 'DEMO_MAP_ID')}
