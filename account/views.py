import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import email_otp, google_auth
from .models import CustomUser
from .services import admin_signup_open, register_user

BACKEND = 'account.auth_backend.EmailBackend'
HOME = {'rider': 'riderpages:index', 'driver': 'driverpages:homepage', 'admin': 'adminpages:home'}
LOGIN_PAGE = {'rider': 'account:rider_login', 'driver': 'account:driver_login', 'admin': 'account:admin_login'}
PENDING_KEY = 'turbo_email_otp'


def first(request):
    return render(request, 'account/usertype.html')


# ---------- email code step (shared by sign-up and login) ----------

def _start_email_check(request, user, next_url='', remember=True):
    """Email a code and send the user to the "check your email" page."""
    purpose = email_otp.purpose_for(user)
    email_otp.send_code(user, purpose)
    request.session[PENDING_KEY] = {'uid': user.pk, 'purpose': purpose, 'next': next_url, 'remember': remember}
    return redirect('account:verify_email')


def _finish_login(request, user, next_url='', remember=True):
    login(request, user, backend=BACKEND)
    if not remember:
        request.session.set_expiry(0)  # expire when the browser closes
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(HOME[user.role])


def verify_email(request):
    pending = request.session.get(PENDING_KEY)
    user = CustomUser.objects.filter(pk=(pending or {}).get('uid'), is_active=True).first() if pending else None
    if user is None:
        messages.info(request, "Please log in to continue.")
        return redirect('account:usertype')
    purpose = pending['purpose']

    if request.method == 'POST':
        if request.POST.get('action') == 'resend':
            try:
                email_otp.send_code(user, purpose)
                messages.success(request, f"A new code was sent to {email_otp.mask_email(user.email)}.")
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
            return redirect('account:verify_email')
        try:
            email_otp.verify_code(user, purpose, request.POST.get('code'))
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect('account:verify_email')
        del request.session[PENDING_KEY]
        if purpose == 'register':
            messages.success(request, "Email verified — welcome to Turbo!")
        return _finish_login(request, user, pending.get('next', ''), pending.get('remember', True))

    return render(request, 'account/verify_email.html', {
        'masked_email': email_otp.mask_email(user.email),
        'purpose': purpose,
        'role': user.role,
        'back_url': LOGIN_PAGE[user.role],
    })


# ---------- SIGNUP ----------

def _signup(request, role, template, login_url_name, label):
    if request.method != 'POST':
        return render(request, template)
    try:
        user = register_user(
            role=role,
            full_name=request.POST.get('full_name'),
            username=request.POST.get('username'),
            email=request.POST.get('email'),
            password=request.POST.get('password1', ''),
            password2=request.POST.get('password2', ''),
        )
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
        return render(request, template, {'form_data': request.POST})

    if role == 'admin' and request.user.is_authenticated:
        # An admin created another admin: they confirm their own email at first login.
        messages.success(request, f"Admin account created for {user.email}.")
        return redirect('adminpages:home')

    if email_otp.enabled():
        try:
            return _start_email_check(request, user)
        except ValidationError as exc:
            messages.error(request, exc.messages[0] + " You can log in to get a new code.")
            return redirect(login_url_name)
    messages.success(request, f"{label} account created successfully! Please log in.")
    return redirect(login_url_name)


def ridersignup(request):
    return _signup(request, 'rider', 'account/ridersignup.html', 'account:rider_login', 'Rider')


def driversignup(request):
    return _signup(request, 'driver', 'account/driversignup.html', 'account:driver_login', 'Driver')


def adminsignup(request):
    # Anyone may create the very first admin; after that only admins can add admins.
    is_admin = request.user.is_authenticated and request.user.role == 'admin'
    if not (is_admin or admin_signup_open()):
        messages.error(request, "Admin accounts can only be created by an existing admin.")
        return redirect('account:admin_login')
    return _signup(request, 'admin', 'account/adminsignup.html', 'account:admin_login', 'Admin')


# ---------- LOGIN / LOGOUT ----------

def _login(request, role, template, label):
    if request.method != 'POST':
        return render(request, template)

    user = authenticate(
        request,
        email=request.POST.get('email', '').strip(),
        password=request.POST.get('password', ''),
    )
    if user is None or user.role != role:
        messages.error(request, f"Invalid email or password for {label}.")
        return render(request, template)

    next_url = request.POST.get('next') or request.GET.get('next') or ''
    remember = bool(request.POST.get('remember'))
    if email_otp.enabled():
        try:
            return _start_email_check(request, user, next_url, remember)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return render(request, template)
    return _finish_login(request, user, next_url, remember)


def riderlogin(request):
    return _login(request, 'rider', 'account/riderlogin.html', 'Rider')


def driverlogin(request):
    return _login(request, 'driver', 'account/driverlogin.html', 'Driver')


def adminlogin(request):
    return _login(request, 'admin', 'account/adminlogin.html', 'Admin')


@require_POST
def google_login(request):
    """Called by the "Continue with Google" button with Google's ID token (CSRF-protected).

    Google has verified the email, so no emailed code is needed. Returns {redirect}.
    """
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        data = {}
    role = data.get('role')
    if role not in HOME:
        return JsonResponse({'detail': 'Unknown account type.'}, status=400)
    try:
        claims = google_auth.verify_id_token(data.get('credential'))
        user, created = google_auth.sign_in(claims, role)
    except ValidationError as exc:
        return JsonResponse({'detail': exc.messages[0]}, status=400)

    request.session.pop(PENDING_KEY, None)
    login(request, user, backend=BACKEND)
    next_url = data.get('next') or ''
    if created:
        if role == 'driver':
            messages.success(request, "Welcome to Turbo! Add your phone, licence and vehicle so you can start taking rides.")
            return JsonResponse({'redirect': reverse('driverpages:edit_profile')})
        messages.success(request, f"Welcome to Turbo, {user.full_name}!")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                                    require_https=request.is_secure()):
        return JsonResponse({'redirect': next_url})
    return JsonResponse({'redirect': reverse(HOME[role])})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('account:usertype')
