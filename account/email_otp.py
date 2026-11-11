"""Email verification codes for registration and login.

* 6 random digits (``secrets``), valid for CODE_TTL, emailed to the account's address.
* Only a keyed hash (HMAC-SHA256 with SECRET_KEY) is stored; codes are single-use.
* 5 wrong tries burn the code; resending is rate-limited (60 s apart, 6 per hour).
* Sending a new code invalidates any earlier unused code for the same purpose.

The website keeps the pending login in the session; the API hands the client a
signed, expiring "challenge" token instead (see make_challenge / read_challenge).
"""
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import CustomUser, EmailOTP

logger = logging.getLogger('turbo.email_otp')

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_SENDS_PER_HOUR = 6
CHALLENGE_SALT = 'turbo.email-otp'
CHALLENGE_MAX_AGE = 30 * 60  # seconds


def enabled():
    return getattr(settings, 'EMAIL_OTP_ENABLED', False)


def purpose_for(user):
    """Unverified accounts first confirm their email; verified ones get a login code."""
    return 'login' if user.email_verified else 'register'


def mask_email(email):
    name, _, domain = email.partition('@')
    shown = name[:2] if len(name) > 3 else name[:1]
    return f"{shown}{'•' * max(len(name) - len(shown), 1)}@{domain}"


def _hash(user_id, purpose, code):
    return hmac.new(settings.SECRET_KEY.encode(), f'email-otp:{user_id}:{purpose}:{code}'.encode(),
                    hashlib.sha256).hexdigest()


def _message(user, purpose, code):
    action = 'finish creating your Turbo account' if purpose == 'register' else 'log in to Turbo'
    minutes = int(CODE_TTL.total_seconds() // 60)
    text = (f"Hi {user.full_name or 'there'},\n\n"
            f"Your Turbo verification code is: {code}\n\n"
            f"Enter it to {action}. It expires in {minutes} minutes.\n"
            "If you didn't request this, you can ignore this email — your account stays safe.\n\n"
            "— Turbo Cab")
    html = f"""<div style="font-family:Inter,Segoe UI,Arial,sans-serif;max-width:480px;margin:auto;padding:24px;color:#111">
  <h2 style="margin:0 0 8px">Your Turbo verification code</h2>
  <p style="color:#555;margin:0 0 20px">Enter this code to {action}.</p>
  <div style="font-size:34px;font-weight:800;letter-spacing:10px;background:#f3f4f6;border-radius:12px;padding:16px;text-align:center">{code}</div>
  <p style="color:#555">It expires in {minutes} minutes. If you didn't request it, ignore this email.</p>
  <p style="color:#999;font-size:12px">Turbo Cab · Kannur, Kerala</p></div>"""
    subject = f"{code} is your Turbo verification code"
    return subject, text, html


def send_code(user, purpose):
    """Email a fresh code. Raises ValidationError if rate-limited or the email can't be sent."""
    now = timezone.now()
    recent = EmailOTP.objects.filter(user=user, purpose=purpose, created_at__gte=now - timedelta(hours=1))
    last = recent.order_by('-created_at').first()
    if last and now - last.created_at < RESEND_COOLDOWN:
        wait = int((RESEND_COOLDOWN - (now - last.created_at)).total_seconds()) + 1
        raise ValidationError(f"Please wait {wait} seconds before requesting another code.", code='cooldown')
    if recent.count() >= MAX_SENDS_PER_HOUR:
        raise ValidationError("Too many codes requested. Try again in an hour.", code='too_many')

    code = f'{secrets.randbelow(10 ** 6):06d}'
    with transaction.atomic():
        # Older unused codes stop working.
        EmailOTP.objects.filter(user=user, purpose=purpose, used_at__isnull=True, expires_at__gt=now) \
            .update(expires_at=now)
        otp = EmailOTP.objects.create(user=user, purpose=purpose, code_hash=_hash(user.pk, purpose, code),
                                      sent_to=user.email, expires_at=now + CODE_TTL)
    subject, text, html = _message(user, purpose, code)
    try:
        send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email], html_message=html, fail_silently=False)
    except Exception as exc:  # SMTP blocked, wrong password, network...
        otp.delete()
        logger.error('Could not send %s code to %s: %s', purpose, user.email, exc)
        raise ValidationError("We couldn't send the verification email right now. Please try again in a minute.",
                              code='send_failed')
    logger.info('Sent %s code to %s', purpose, user.email)
    return otp


def verify_code(user, purpose, code):
    """Check a code. On success it's used up (and registration marks the email verified)."""
    code = ''.join(ch for ch in str(code or '') if ch.isdigit())
    now = timezone.now()
    with transaction.atomic():
        otp = (EmailOTP.objects.select_for_update()
               .filter(user=user, purpose=purpose, used_at__isnull=True).order_by('-created_at').first())
        if otp is None or otp.expires_at <= now:
            raise ValidationError("This code has expired. Tap \"Resend code\" to get a new one.", code='expired')
        if otp.attempts >= MAX_ATTEMPTS:
            raise ValidationError("Too many wrong attempts. Tap \"Resend code\" to get a new one.", code='locked')
        if len(code) != 6 or not hmac.compare_digest(otp.code_hash, _hash(user.pk, purpose, code)):
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            left = MAX_ATTEMPTS - otp.attempts
            ok = False
        else:
            otp.used_at = now
            otp.save(update_fields=['used_at'])
            if purpose == 'register' and not user.email_verified:
                CustomUser.objects.filter(pk=user.pk).update(email_verified=True)
                user.email_verified = True
            ok = True
    if not ok:
        msg = f"Incorrect code. {left} attempt{'s' if left != 1 else ''} left." if left > 0 else \
            "Too many wrong attempts. Tap \"Resend code\" to get a new one."
        raise ValidationError(msg, code='wrong' if left > 0 else 'locked')
    return user


# ---------------------------------------------------------------- API challenge tokens

def make_challenge(user, purpose):
    return signing.dumps({'u': user.pk, 'p': purpose}, salt=CHALLENGE_SALT)


def read_challenge(token):
    try:
        data = signing.loads(token or '', salt=CHALLENGE_SALT, max_age=CHALLENGE_MAX_AGE)
        user = CustomUser.objects.get(pk=data['u'], is_active=True)
    except (signing.BadSignature, CustomUser.DoesNotExist, KeyError, TypeError):
        raise ValidationError("This verification has expired. Please log in again.", code='bad_challenge')
    return user, data['p']
