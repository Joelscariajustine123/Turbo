# driverpages/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count
from django.db.models.functions import TruncDay

from .models import DriverProfile, Earning, AvailabilityStatus
# Import the unified Ride model from the riderpages app
from riderpages.models import Ride

@login_required
def homepage(request):
    driver_profile = get_object_or_404(DriverProfile, user=request.user)
    
    # --- UPDATED: Fetch both new and ongoing rides ---
    available_rides = Ride.objects.filter(status='CONFIRMED', driver__isnull=True)
    ongoing_rides = Ride.objects.filter(driver=driver_profile, status='ACCEPTED')

    context = {
        'driver': driver_profile,
        'ride_requests': available_rides,
        'ongoing_rides': ongoing_rides, # Pass ongoing rides to the template
    }
    return render(request, 'driverpages/homepage.html', context)

@login_required
def accept_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    driver_profile = get_object_or_404(DriverProfile, user=request.user)
    if ride.status == 'CONFIRMED' and ride.driver is None:
        ride.driver = driver_profile
        ride.status = 'ACCEPTED'
        ride.save()
        
        Earning.objects.create(
            driver=driver_profile,
            ride=ride,
            amount=ride.fare,
            date=timezone.now().date()
        )
        messages.success(request, "Ride accepted! It is now listed under 'Ongoing Rides'.")
    else:
        messages.error(request, "This ride is no longer available.")
    return redirect('driverpages:homepage')

# --- NEW: View to mark a ride as complete ---
@login_required
def complete_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, driver__user=request.user)
    if ride.status == 'ACCEPTED':
        ride.status = 'COMPLETED'
        ride.save()
        messages.success(request, "Ride marked as complete!")
    else:
        messages.error(request, "This ride cannot be marked as complete.")
    return redirect('driverpages:homepage')


@login_required
def decline_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    if ride.status == 'CONFIRMED':
        ride.status = 'CANCELLED'
        ride.save()
        messages.info(request, "The ride has been declined.")
    else:
        messages.error(request, "This ride cannot be declined.")
    return redirect('driverpages:homepage')

@login_required
def earnings(request):
    driver = get_object_or_404(DriverProfile, user=request.user)
    now = timezone.now().date()
    
    earnings_qs = Earning.objects.filter(driver=driver)
    
    # This will now show the correct count
    completed_rides = Ride.objects.filter(driver=driver, status='COMPLETED').count()

    # Calculate totals
    total_earnings = earnings_qs.aggregate(Sum('amount'))['amount__sum'] or 0
    daily_earnings = earnings_qs.filter(date=now).aggregate(Sum('amount'))['amount__sum'] or 0
    weekly_earnings = earnings_qs.filter(date__gte=now - timedelta(days=7)).aggregate(Sum('amount'))['amount__sum'] or 0
    monthly_earnings = earnings_qs.filter(date__gte=now - timedelta(days=30)).aggregate(Sum('amount'))['amount__sum'] or 0
    
    all_earnings = earnings_qs.select_related('ride', 'ride__user').order_by('-date')
    
    context = {
        'driver': driver,
        'total_earnings': total_earnings,
        'daily_earnings': daily_earnings,
        'weekly_earnings': weekly_earnings,
        'monthly_earnings': monthly_earnings,
        'completed_rides': completed_rides,
        'all_earnings': all_earnings,
    }
    return render(request, 'driverpages/earning.html', context)

@login_required
def profile(request):
    driver = get_object_or_404(DriverProfile, user=request.user)
    if request.method == 'POST' and request.FILES.get('profile_photo'):
        driver.profile_photo = request.FILES['profile_photo']
        driver.save()
        return redirect('driverpages:profile')
    return render(request, 'driverpages/profile.html', {'driver': driver})

@login_required
def edit_profile(request):
    driver = get_object_or_404(DriverProfile, user=request.user)
    user = request.user
    if request.method == 'POST':
        user.full_name = request.POST.get('full_name')
        user.phone = request.POST.get('phone')
        user.email = request.POST.get('email')
        user.save()

        driver.license_number = request.POST.get('license_number')
        driver.vehicle_info = request.POST.get('vehicle_info')
        driver.availability_status = request.POST.get('availability_status')
        if request.FILES.get('profile_photo'):
            driver.profile_photo = request.FILES.get('profile_photo')
        driver.save()
        return redirect('driverpages:profile')
    return render(request, 'driverpages/edit_profile.html', {'driver': driver})
