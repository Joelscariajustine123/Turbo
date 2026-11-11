"""Account rules shared by the website views and the REST API."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import CustomUser

SELF_SIGNUP_ROLES = ('rider', 'driver')


def admin_signup_open():
    """Public admin signup is only allowed until the first admin exists."""
    return not CustomUser.objects.filter(role='admin').exists()


def validate_phone(phone):
    if phone and (not phone.isdigit() or len(phone) != 10):
        raise ValidationError("Phone number must be exactly 10 digits.")


def check_email_free(email, exclude_user=None):
    qs = CustomUser.objects.filter(email__iexact=email)
    if exclude_user is not None:
        qs = qs.exclude(pk=exclude_user.pk)
    if qs.exists():
        raise ValidationError("An account with this email already exists.")


def register_user(*, role, full_name, username, email, password, password2=None, phone=''):
    full_name = (full_name or '').strip()
    username = (username or '').strip()
    email = (email or '').strip().lower()
    phone = (phone or '').strip()

    errors = []
    if not (full_name and username and email and password):
        errors.append("All fields are required.")
    if password2 is not None and password != password2:
        errors.append("Passwords do not match.")
    if email:
        try:
            validate_email(email)
            check_email_free(email)
        except ValidationError as exc:
            errors.extend(exc.messages)
    if username and CustomUser.objects.filter(username__iexact=username).exists():
        errors.append("Username is already taken. Please choose another one.")
    try:
        validate_phone(phone)
    except ValidationError as exc:
        errors.extend(exc.messages)
    if not errors:
        try:
            validate_password(password, user=CustomUser(username=username, email=email, full_name=full_name))
        except ValidationError as exc:
            errors.extend(exc.messages)
    if errors:
        raise ValidationError(errors)

    extra = {'phone': phone} if phone else {}
    return CustomUser.objects.create_user(
        username=username, email=email, password=password,
        full_name=full_name, role=role, **extra,
    )
