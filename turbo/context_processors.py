from django.conf import settings


def google_signin(request):
    """GOOGLE_CLIENT_ID for the "Continue with Google" button (empty = button hidden)."""
    return {'GOOGLE_CLIENT_ID': getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')}
