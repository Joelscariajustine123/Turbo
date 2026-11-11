from django.conf import settings


def google_signin(request):
    """GOOGLE_CLIENT_ID for the "Continue with Google" button (empty = button hidden), and the
    Search Console ownership token (meta tag on the homepage)."""
    return {
        'GOOGLE_CLIENT_ID': getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', ''),
        'GOOGLE_SITE_VERIFICATION': getattr(settings, 'GOOGLE_SITE_VERIFICATION', ''),
    }
