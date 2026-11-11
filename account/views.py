from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .services import admin_signup_open, register_user


def first(request):
    return render(request, 'account/usertype.html')


# ---------- SIGNUP ----------

def _signup(request, role, template, login_url_name, label):
    if request.method != 'POST':
        return render(request, template)
    try:
        register_user(
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

    messages.success(request, f"{label} account created successfully!")
    if role == 'admin' and request.user.is_authenticated:
        return redirect('adminpages:home')  # an admin created another admin
    messages.info(request, "Please log in.")
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

def _login(request, role, template, default_redirect, label):
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

    login(request, user)
    if not request.POST.get('remember'):
        request.session.set_expiry(0)  # expire when the browser closes

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(default_redirect)


def riderlogin(request):
    return _login(request, 'rider', 'account/riderlogin.html', 'riderpages:index', 'Rider')


def driverlogin(request):
    return _login(request, 'driver', 'account/driverlogin.html', 'driverpages:homepage', 'Driver')


def adminlogin(request):
    return _login(request, 'admin', 'account/adminlogin.html', 'adminpages:home', 'Admin')


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('account:usertype')
