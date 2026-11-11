from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from account.decorators import role_required
from account.forms import EditRiderForm
from account.models import CustomUser
from riderpages.models import Ride

from . import services

admin_required = role_required('admin')


@admin_required
def home(request):
    return render(request, 'adminpages/home.html', services.dashboard_stats())


@admin_required
def dashboard(request):
    recent_rides = Ride.objects.select_related('user').order_by('-created_at')[:5]
    return render(request, 'adminpages/dashboard.html', {'recent_rides': recent_rides})


@admin_required
def booking(request):
    rides = list(Ride.objects.select_related('user').order_by('-created_at'))
    return render(request, 'adminpages/booking.html', {'rides': rides, 'ride_count': len(rides)})


@admin_required
def payment(request):
    payments = (
        Ride.objects.select_related('user')
        .filter(fare__isnull=False)
        .order_by('-created_at')
    )
    return render(request, 'adminpages/payment.html', {'payments': payments})


@admin_required
def report(request):
    return render(request, 'adminpages/report.html', {'reports': services.daily_reports()})


@admin_required
def rider(request):
    riders = list(CustomUser.objects.filter(role='rider').order_by('-date_joined'))
    return render(request, 'adminpages/rider.html', {'riders': riders, 'rider_count': len(riders)})


@admin_required
def settings(request):
    user = request.user

    if request.method == 'POST':
        full_name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        errors = []
        if not full_name or not email:
            errors.append("Name and email are required.")
        elif CustomUser.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            errors.append("That email is already used by another account.")
        if password:
            try:
                validate_password(password, user=user)
            except ValidationError as exc:
                errors.extend(exc.messages)

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            user.full_name = full_name
            user.email = email
            if password:
                user.set_password(password)
            user.save()
            if password:
                update_session_auth_hash(request, user)  # keep the admin logged in
            messages.success(request, "Account settings updated successfully.")
            return redirect('adminpages:settings')

    return render(request, 'adminpages/settings.html')


@admin_required
@require_POST
def delete_rider(request, rider_id):
    rider_obj = get_object_or_404(CustomUser, id=rider_id, role='rider')
    rider_obj.delete()
    messages.success(request, "Rider deleted successfully.")
    return redirect('adminpages:rider')


@admin_required
def edit_rider(request, rider_id):
    rider_obj = get_object_or_404(CustomUser, id=rider_id, role='rider')
    if request.method == 'POST':
        form = EditRiderForm(request.POST, instance=rider_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Rider updated successfully.")
            return redirect('adminpages:rider')
    else:
        form = EditRiderForm(instance=rider_obj)
    return render(request, 'adminpages/edit_rider.html', {'form': form})
