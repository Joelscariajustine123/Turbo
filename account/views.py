from django.shortcuts import render

# Create your views here.
def first(request):
    return render(request,'account/usertype.html')

# def riderlogin(request):
#     return render(request,'account/riderlogin.html')

# def dirverlogin(request):
#     return render(request,'account/driverlogin.html')

# def adminlogin(request):
#     return render(request,'account/adminlogin.html')

# def ridersignup(request):
#     return render(request,'account/ridersignup.html')

# def driversignup(request):
#     return render(request,'account/driversignup.html')

# def adminsignup(request):
#     return render(request,'account/adminsignup.html')

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.hashers import make_password
from .models import CustomUser


# ---------- SIGNUP VIEWS ----------

def ridersignup(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return render(request, 'account/ridersignup.html')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return render(request, 'account/ridersignup.html')

        user = CustomUser.objects.create(
            full_name=full_name,
            email=email,
            username=email,
            password=make_password(password1),
            role='rider'
        )
        messages.success(request, "Rider account created successfully!")
        return redirect('rider_login')

    return render(request, 'account/ridersignup.html')


def driversignup(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return render(request, 'account/driversignup.html')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return render(request, 'account/driversignup.html')

        user = CustomUser.objects.create(
            full_name=full_name,
            email=email,
            username=email,
            password=make_password(password1),
            role='driver'
        )
        messages.success(request, "Driver account created successfully!")
        return redirect('driver_login')

    return render(request, 'account/driversignup.html')


def adminsignup(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return render(request, 'account/adminsignup.html')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return render(request, 'account/adminsignup.html')

        user = CustomUser.objects.create(
            full_name=full_name,
            email=email,
            username=email,
            password=make_password(password1),
            role='admin'
        )
        messages.success(request, "Admin account created successfully!")
        return redirect('admin_login')

    return render(request, 'account/adminsignup.html')


# ---------- LOGIN VIEWS ----------

def riderlogin(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)
        if user is not None and user.role == 'rider':
            login(request, user)
            return redirect('rider_dashboard')  # define this
        else:
            messages.error(request, "Invalid login credentials for Rider")
            return render(request, 'account/riderlogin.html')

    return render(request, 'account/riderlogin.html')


def driverlogin(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)
        if user is not None and user.role == 'driver':
            login(request, user)
            return redirect('driver_dashboard')  # define this
        else:
            messages.error(request, "Invalid login credentials for Driver")
            return render(request, 'account/driverlogin.html')

    return render(request, 'account/driverlogin.html')


def adminlogin(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)
        if user is not None and user.role == 'admin':
            login(request, user)
            return redirect('admin_dashboard')  # define this
        else:
            messages.error(request, "Invalid login credentials for Admin")
            return render(request, 'account/adminlogin.html')

    return render(request, 'account/adminlogin.html')
