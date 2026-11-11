"""Pickup verification codes (OTP).

How it works
------------
* When a driver accepts a ride, a RideOTP row is created with a random nonce
  (``secrets.token_hex``). The 6-digit code is HMAC-SHA256(SECRET_KEY, ride:nonce)
  reduced to 6 digits, so it is uniformly random and only the server can derive it.
* Nothing in the database reveals the code: the rider's code is re-derived on
  request, and the driver's entry is compared against ``otp_hash`` (a keyed hash)
  in constant time.
* Codes expire (TURBO_OTP_TTL_MINUTES, default 10). A fresh code is issued when
  the driver marks "arrived", so the window starts when it is actually needed.
* 5 wrong attempts lock verification for TURBO_OTP_LOCK_MINUTES (default 10).
  The rider can request a new code, which invalidates the old one.
* Every attempt is written to OTPAttempt.
"""
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import OTPAttempt, RideOTP

logger = logging.getLogger('turbo.otp')

OTP_DIGITS = 6
MAX_ATTEMPTS = 5
REGENERATE_COOLDOWN = timedelta(seconds=30)


def ttl():
    return timedelta(minutes=getattr(settings, 'TURBO_OTP_TTL_MINUTES', 10))


def lock_duration():
    return timedelta(minutes=getattr(settings, 'TURBO_OTP_LOCK_MINUTES', 10))


def _key():
    return settings.SECRET_KEY.encode()


def _derive_code(ride_id, nonce):
    mac = hmac.new(_key(), f'otp:{ride_id}:{nonce}'.encode(), hashlib.sha256).digest()
    return str(int.from_bytes(mac, 'big') % 10 ** OTP_DIGITS).zfill(OTP_DIGITS)


def _hash_code(ride_id, code):
    return hmac.new(_key(), f'verify:{ride_id}:{code}'.encode(), hashlib.sha256).hexdigest()


def issue(ride):
    """Create (or replace) the ride's OTP. Any previous code stops working."""
    nonce = secrets.token_hex(16)
    now = timezone.now()
    otp, created = RideOTP.objects.update_or_create(
        ride=ride,
        defaults={
            'nonce': nonce,
            'otp_hash': _hash_code(ride.pk, _derive_code(ride.pk, nonce)),
            'expires_at': now + ttl(),
            'attempts': 0,
            'locked_until': None,
            'is_verified': False,
            'verified_at': None,
            'created_at': now,
        },
    )
    if not created:
        RideOTP.objects.filter(pk=otp.pk).update(regenerated_count=otp.regenerated_count + 1)
    return otp


@dataclass
class RiderOTPView:
    code: str
    expires_at: object
    is_expired: bool
    is_locked: bool
    locked_until: object
    attempts_left: int

    def as_dict(self):
        return {
            'otp': None if self.is_expired else self.code,
            'expires_at': self.expires_at,
            'is_expired': self.is_expired,
            'is_locked': self.is_locked,
            'locked_until': self.locked_until,
            'attempts_left': self.attempts_left,
        }


def for_rider(ride):
    """The code to show the rider, or None if there is nothing to show."""
    otp = RideOTP.objects.filter(ride=ride).first()
    if otp is None or otp.is_verified or ride.otp_verified:
        return None
    now = timezone.now()
    locked = bool(otp.locked_until and otp.locked_until > now)
    return RiderOTPView(
        code=_derive_code(ride.pk, otp.nonce),
        expires_at=otp.expires_at,
        is_expired=otp.expires_at <= now,
        is_locked=locked,
        locked_until=otp.locked_until if locked else None,
        attempts_left=max(MAX_ATTEMPTS - otp.attempts, 0),
    )


def regenerate(ride):
    """Rider asks for a new code (old code is invalidated). Rate-limited."""
    from django.core.exceptions import ValidationError

    if ride.otp_verified or ride.status not in ('ACCEPTED', 'ARRIVED'):
        raise ValidationError("A new code is only available before the ride starts.")
    otp = RideOTP.objects.filter(ride=ride).first()
    if otp is not None and timezone.now() - otp.created_at < REGENERATE_COOLDOWN:
        raise ValidationError("Please wait a few seconds before requesting another code.")
    logger.info('OTP regenerated for ride %s', ride.pk)
    return issue(ride)


@dataclass
class VerifyResult:
    ok: bool
    reason: str = ''
    message: str = ''
    attempts_left: int = 0


def verify(ride, driver, code, ip_address=None):
    """Check a code entered by the driver. Caller must already hold a lock on `ride`.

    Returns a VerifyResult (never raises for a wrong code) so the failed-attempt
    counter is saved even though the overall request fails.
    """
    code = ''.join(ch for ch in str(code or '') if ch.isdigit())
    now = timezone.now()

    with transaction.atomic():
        otp = RideOTP.objects.select_for_update().filter(ride=ride).first()

        def done(ok, reason, message, attempts_left=0):
            OTPAttempt.objects.create(ride=ride, driver=driver, success=ok, reason=reason, ip_address=ip_address)
            (logger.info if ok else logger.warning)('OTP %s for ride %s by driver %s', reason, ride.pk, driver.pk)
            return VerifyResult(ok, reason, message, attempts_left)

        if otp is None:
            return done(False, 'missing', "No verification code exists for this ride. Ask the rider to refresh their code.")
        if otp.is_verified:
            return done(False, 'reused', "This code has already been used.")
        if otp.locked_until and otp.locked_until > now:
            minutes = max(1, int((otp.locked_until - now).total_seconds() // 60) + 1)
            return done(False, 'locked', f"Too many wrong attempts. Try again in {minutes} min, "
                                         "or ask the rider to get a new code.")
        if otp.expires_at <= now:
            return done(False, 'expired', "This code has expired. Ask the rider to tap \"Get a new code\".")
        if len(code) != OTP_DIGITS:
            return done(False, 'malformed', "Enter the 6-digit code from the rider's screen.",
                        MAX_ATTEMPTS - otp.attempts)

        if not hmac.compare_digest(otp.otp_hash, _hash_code(ride.pk, code)):
            otp.attempts += 1
            left = MAX_ATTEMPTS - otp.attempts
            if left <= 0:
                otp.locked_until = now + lock_duration()
                otp.save(update_fields=['attempts', 'locked_until'])
                return done(False, 'locked', "Too many wrong attempts. Verification is locked for "
                                             f"{int(lock_duration().total_seconds() // 60)} minutes.")
            otp.save(update_fields=['attempts'])
            return done(False, 'wrong', f"Incorrect code. {left} attempt{'s' if left != 1 else ''} left.", left)

        otp.is_verified = True
        otp.verified_at = now
        otp.save(update_fields=['is_verified', 'verified_at'])
        return done(True, 'verified', "Passenger verified. Ride started.")
