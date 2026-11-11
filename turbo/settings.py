"""
Django settings for the Turbo Cab project.

Local development works with no configuration (SQLite, DEBUG on).
Production (e.g. Render) is configured through environment variables — see
README.md and render.yaml.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=''):
    return [v.strip() for v in os.environ.get(name, default).split(',') if v.strip()]


def env_bool(name, default):
    return os.environ.get(name, str(default)).lower() in ('1', 'true', 'yes', 'on')


# ---------------------------------------------------------------------------
# Core / security
# ---------------------------------------------------------------------------
DEBUG = env_bool('DJANGO_DEBUG', True)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('Set DJANGO_SECRET_KEY when DJANGO_DEBUG is False.')
    SECRET_KEY = 'django-insecure-ls3-1wdv61frg2f4=fo99bnw*n_o*7gfu-%t)l9!#$$0(hf0=@'  # local dev only

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,10.0.2.2')
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

# Render sets this to the service's public hostname (xyz.onrender.com).
RENDER_HOST = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_HOST}')

if not DEBUG:
    # Render terminates HTTPS in front of the app and forwards this header.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SSL_REDIRECT', True)
    SECURE_REDIRECT_EXEMPT = [r'^api/meta/$']  # health check
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', 3600))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Send only our origin (never the path) to other sites. OpenStreetMap's tile
    # servers block map tiles requested without a Referer, so 'same-origin' breaks the map.
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'account',
    'adminpages',
    'driverpages',
    'riderpages',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serves static files + the React app
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'turbo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'turbo.wsgi.application'


# ---------------------------------------------------------------------------
# Database: DATABASE_URL (Postgres on Render) or local SQLite
# ---------------------------------------------------------------------------
if os.environ.get('DATABASE_URL'):
    DATABASES = {'default': dj_database_url.config(conn_max_age=600, conn_health_checks=True)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get('DJANGO_DB_PATH', BASE_DIR / 'db.sqlite3'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('DJANGO_TIME_ZONE', 'Asia/Kolkata')
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files, React app and uploads
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        # Hashed, compressed file names in production so browsers can cache them forever.
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
        else 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# The built React app (frontend/dist/app/...) is served at /app/ by WhiteNoise.
REACT_BUILD_DIR = BASE_DIR / 'frontend' / 'dist'
if REACT_BUILD_DIR.is_dir():
    WHITENOISE_ROOT = REACT_BUILD_DIR


def _immutable_file_test(path, url):
    """Files whose name contains a content hash never change, so browsers may cache them forever."""
    import re
    return bool(
        # Django collectstatic: home.14fd02a8213c.css
        re.search(r'\.[0-9a-f]{12}\.\w+$', url)
        # Vite (React build): /app/assets/index-CopzS8fx.js
        or re.search(r'/assets/[^/]+-[A-Za-z0-9_-]{8}\.\w+$', url)
    )


WHITENOISE_IMMUTABLE_FILE_TEST = _immutable_file_test

MEDIA_URL = '/media/'
# On Render, point this at a persistent disk (paid plans), otherwise uploads
# are lost when the service restarts or redeploys.
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', BASE_DIR / 'media'))
SERVE_MEDIA = env_bool('DJANGO_SERVE_MEDIA', True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'account.CustomUser'
AUTHENTICATION_BACKENDS = ['account.auth_backend.EmailBackend']  # log in with email + password

# Role-specific pages use account.decorators.role_required, which sends users
# to the right login page. This is only the fallback for plain @login_required.
LOGIN_URL = 'account:usertype'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
}


# ---------------------------------------------------------------------------
# REST API (used by the React frontend and the Flutter apps)
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # React + mobile apps
        'rest_framework.authentication.SessionAuthentication',        # Django website pages (CSRF-protected)
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer']
    + (['rest_framework.renderers.BrowsableAPIRenderer'] if DEBUG else []),
    'DEFAULT_CONTENT_NEGOTIATION_CLASS': 'api.negotiation.JSONFallbackNegotiation',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'api.exceptions.exception_handler',
    'DEFAULT_THROTTLE_RATES': {
        'auth': '20/min',
        'location': '45/min',    # drivers send a GPS fix every 3 s (20/min)
        'tracking': '90/min',    # riders poll every 3 s, allow a couple of tabs
        'otp': '15/min',
    },
    'COERCE_DECIMAL_TO_STRING': False,  # send prices as JSON numbers
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=14),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
}

# Browser origins allowed to call the API from *another* site (the React dev
# server by default). The hosted React app is same-origin, and mobile apps are
# not browsers, so neither needs an entry here.
CORS_ALLOWED_ORIGINS = env_list('DJANGO_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
CORS_URLS_REGEX = r'^/(api|media)/.*$'

# Road-distance routing server for fares (OSRM). Set TURBO_ROUTING_URL to '' to
# always use the straight-line estimate instead.
ROUTING_URL = os.environ.get('TURBO_ROUTING_URL', 'https://router.project-osrm.org')
ROUTING_TIMEOUT = 5

# UPI ID shown to riders for payment
UPI_ID = os.environ.get('TURBO_UPI_ID', 'joeljustine@ybl')

# ---------------------------------------------------------------------------
# Live tracking + pickup OTP
# ---------------------------------------------------------------------------
# Google Maps for the live maps. Leave empty to use OpenStreetMap (no key needed).
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')
GOOGLE_MAPS_MAP_ID = os.environ.get('GOOGLE_MAPS_MAP_ID', 'DEMO_MAP_ID')  # needed for Advanced Markers
TURBO_OTP_TTL_MINUTES = int(os.environ.get('TURBO_OTP_TTL_MINUTES', 10))
TURBO_OTP_LOCK_MINUTES = int(os.environ.get('TURBO_OTP_LOCK_MINUTES', 10))
TURBO_TRACK_RETENTION_DAYS = int(os.environ.get('TURBO_TRACK_RETENTION_DAYS', 30))  # breadcrumb history

# Driver must be this close (live GPS) to tap "Arrived" at pickup / "Complete" at the drop.
TURBO_GEOFENCE_RADIUS_M = int(os.environ.get('TURBO_GEOFENCE_RADIUS_M', 50))

# ---------------------------------------------------------------------------
# Email (verification codes for register + login)
# ---------------------------------------------------------------------------
# Gmail: EMAIL_HOST_USER=you@gmail.com, EMAIL_HOST_PASSWORD=<16-char app password>.
# NOTE: Render's free plan blocks SMTP ports, so Gmail only works on a paid instance.
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '').replace(' ', '')  # app passwords are shown with spaces
EMAIL_TIMEOUT = 15
EMAIL_CONFIGURED = bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)
EMAIL_BACKEND = ('django.core.mail.backends.smtp.EmailBackend' if EMAIL_CONFIGURED
                 else 'django.core.mail.backends.console.EmailBackend')  # dev: codes printed in the server console
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL',
                                    f'Turbo Cab <{EMAIL_HOST_USER}>' if EMAIL_HOST_USER else 'Turbo Cab <no-reply@turbocab.local>')

# Require emailed codes at register/login?  on | off | auto (default).
# auto = on when email is configured (or in local DEBUG, where codes go to the console),
# so a deploy without email settings never locks everyone out.
_otp_mode = os.environ.get('TURBO_EMAIL_OTP', 'auto').lower()
EMAIL_OTP_ENABLED = {'on': True, 'off': False}.get(_otp_mode, EMAIL_CONFIGURED or DEBUG)

# Tests never call the external routing server, and always exercise email codes.
if 'test' in sys.argv:
    ROUTING_URL = ''
    EMAIL_OTP_ENABLED = True
