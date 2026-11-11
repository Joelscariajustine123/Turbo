"""Sign in with Google (Google Identity Services).

The browser shows Google's button and receives a signed **ID token** (a JWT). We
never trust what the browser says about the user; the server verifies the token:

* signature against Google's published keys (JWKS, cached ~1 h),
* ``aud`` == our GOOGLE_OAUTH_CLIENT_ID, ``iss`` == Google, not expired,
* ``email_verified`` is true.

Then the account is found by Google ID (``sub``), else by email (and linked), else
created (riders/drivers only). Google has confirmed the email, so no emailed code is
needed for Google sign-ins.
"""
import logging
import re

import jwt
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import CustomUser

logger = logging.getLogger('turbo.google_auth')

GOOGLE_ISSUERS = ('accounts.google.com', 'https://accounts.google.com')
GOOGLE_JWKS_URL = 'https://www.googleapis.com/oauth2/v3/certs'
SELF_SIGNUP_ROLES = ('rider', 'driver')
_jwk_client = None


def client_id():
    return getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')


def enabled():
    return bool(client_id())


def _keys():
    global _jwk_client
    if _jwk_client is None:
        _jwk_client = jwt.PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, lifespan=3600, timeout=10)
    return _jwk_client


def verify_id_token(token):
    """Return the token's claims, or raise ValidationError."""
    if not enabled():
        raise ValidationError("Google sign-in isn't set up on this site.", code='disabled')
    if not token or not isinstance(token, str):
        raise ValidationError("Google sign-in failed. Please try again.", code='missing')
    try:
        key = _keys().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token, key, algorithms=['RS256'], audience=client_id(), leeway=60,
            options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']},
        )
    except jwt.ExpiredSignatureError:
        raise ValidationError("Your Google sign-in expired. Please try again.", code='expired')
    except (jwt.PyJWTError, ValueError) as exc:
        logger.warning('Rejected Google ID token: %s', exc)
        raise ValidationError("Google sign-in failed. Please try again.", code='invalid')
    if claims.get('iss') not in GOOGLE_ISSUERS:
        raise ValidationError("Google sign-in failed. Please try again.", code='issuer')
    if not claims.get('email') or claims.get('email_verified') is not True:
        raise ValidationError("Your Google account's email isn't verified.", code='unverified')
    return claims


def _unique_username(email):
    base = re.sub(r'[^\w.@+-]', '', email.split('@')[0])[:140] or 'user'
    name, n = base, 1
    while CustomUser.objects.filter(username__iexact=name).exists():
        n += 1
        name = f'{base}{n}'
    return name


def sign_in(claims, role):
    """Find, link or create the account for verified Google claims. Returns (user, created)."""
    sub = str(claims['sub'])
    email = claims['email'].strip().lower()

    user = CustomUser.objects.filter(google_sub=sub).first()
    if user is None:
        user = CustomUser.objects.filter(email__iexact=email).first()
        if user is not None and user.google_sub and user.google_sub != sub:
            raise ValidationError("This email is linked to a different Google account.", code='other_google')

    created = False
    if user is None:
        if role not in SELF_SIGNUP_ROLES:
            raise ValidationError("No admin account uses this Google email. Admins are added by an existing admin.",
                                  code='no_account')
        try:
            with transaction.atomic():
                user = CustomUser(
                    username=_unique_username(email), email=email, role=role,
                    full_name=(claims.get('name') or email.split('@')[0])[:100],
                    email_verified=True, google_sub=sub,
                )
                user.set_unusable_password()  # Google-only until they choose to set a password
                user.save()
        except IntegrityError:
            raise ValidationError("Couldn't create your account. Please try again.", code='conflict')
        created = True
        logger.info('Created %s account %s via Google', role, email)
    else:
        if user.role != role:
            raise ValidationError(f"This Google account is registered as a {user.role}. "
                                  f"Use the {user.role} login instead.", code='wrong_role')
        if not user.is_active:
            raise ValidationError("This account has been deactivated.", code='inactive')
        changed = []
        if not user.google_sub:
            user.google_sub = sub
            changed.append('google_sub')
        if not user.email_verified:
            user.email_verified = True  # Google confirmed the address
            changed.append('email_verified')
        if changed:
            user.save(update_fields=changed)
    return user, created
