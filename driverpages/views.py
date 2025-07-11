# from django.shortcuts import render
# from django.utils import timezone
# from datetime import timedelta
# from .models import Ride



# def homepage(request):
#     return render(request,'driverpages/homepage.html')


# def earnings(request):
#     driver = request.user  # Make sure the user is authenticated
#     now = timezone.now()

#     # All rides by the driver
#     rides = Ride.objects.filter(driver=driver)

#     # Total earnings
#     total_earnings = rides.aggregate(Sum('amount'))['amount__sum'] or 0

#     # Weekly earnings (last 7 days)
#     week_ago = now - timedelta(days=7)
#     weekly_earnings = rides.filter(completed_at__gte=week_ago).aggregate(Sum('amount'))['amount__sum'] or 0

#     # Monthly earnings (last 30 days)
#     month_ago = now - timedelta(days=30)
#     monthly_earnings = rides.filter(completed_at__gte=month_ago).aggregate(Sum('amount'))['amount__sum'] or 0

#     # Total completed rides
#     completed_rides = rides.count()

#     # Weekly grouped data for chart
#     weekly_data = (
#         rides
#         .annotate(week=TruncWeek('completed_at'))
#         .values('week')
#         .annotate(total=Sum('amount'))
#         .order_by('week')
#     )

#     chart_labels = [entry['week'].strftime("Week of %b %d") for entry in weekly_data]
#     chart_data = [float(entry['total']) for entry in weekly_data]

#     context = {
#         'total_earnings': total_earnings,
#         'weekly_earnings': weekly_earnings,
#         'monthly_earnings': monthly_earnings,
#         'completed_rides': completed_rides,
#         'chart_labels': chart_labels,
#         'chart_data': chart_data,
#     }

#     return render(request, 'driverpages/earning.html', context)

# def profile(request):
#     return render(request,'driverpages/profile.html')

# def setting(request):
#     return render(request,'driverpages/settings.html')



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from django.db.models.functions import TruncWeek
from .models import AvailabilityStatus
from .models import DriverProfile, Ride, Earning
from .forms import DriverProfileForm  # We'll define this form too




@login_required
def homepage(request):
    driver = get_object_or_404(DriverProfile, user=request.user)

    # Handle profile photo upload
    if request.method == 'POST' and request.FILES.get('profile_photo'):
        driver.profile_photo = request.FILES['profile_photo']
        driver.save()
        return redirect('driverpages:homepage')  # Replace with your URL name

    ride_requests = Ride.objects.filter(driver=driver, is_accepted=False, is_completed=False)

    return render(request, 'driverpages/homepage.html', {
        'driver': driver,
        'ride_requests': ride_requests,
    })

@login_required
def earnings(request):
    driver = get_object_or_404(DriverProfile, user=request.user)
    now = timezone.now().date()  # date only

    earnings = Earning.objects.filter(driver=driver)

    # Totals
    total_earnings = earnings.aggregate(Sum('amount'))['amount__sum'] or 0
    weekly_earnings = earnings.filter(date__gte=now - timedelta(days=7)).aggregate(Sum('amount'))['amount__sum'] or 0
    monthly_earnings = earnings.filter(date__gte=now - timedelta(days=30)).aggregate(Sum('amount'))['amount__sum'] or 0
    completed_rides = earnings.count()  # Assuming each earning = 1 completed ride

    # Weekly chart data
    weekly_data = (
        earnings
        .annotate(week=TruncWeek('date'))
        .values('week')
        .annotate(total=Sum('amount'))
        .order_by('week')
    )

    chart_labels = [entry['week'].strftime("Week of %b %d") for entry in weekly_data]
    chart_data = [float(entry['total']) for entry in weekly_data]

    return render(request, 'driverpages/earning.html', {
        'driver': driver,
        'total_earnings': total_earnings,
        'weekly_earnings': weekly_earnings,
        'monthly_earnings': monthly_earnings,
        'completed_rides': completed_rides,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    })

@login_required
def profile(request):
    driver = get_object_or_404(DriverProfile, user=request.user)
    availability_choices = AvailabilityStatus.choices
    return render(request, 'driverpages/profile.html', {
        'driver': driver,
        'availability_choices': availability_choices,
    })

@login_required
def edit_profile(request):
    driver = get_object_or_404(DriverProfile, user=request.user)
    user = request.user

    if request.method == 'POST':
        # Get data from HTML fields
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        license_number = request.POST.get('license_number')
        vehicle_info = request.POST.get('vehicle_info')
        availability_status = request.POST.get('availability_status')
        profile_photo = request.FILES.get('profile_photo')

        # Update User model
        user.full_name = full_name
        user.phone = phone
        user.email = email
        user.save()

        # Update DriverProfile model
        driver.license_number = license_number
        driver.vehicle_info = vehicle_info
        driver.availability_status = availability_status
        if profile_photo:
            driver.profile_photo = profile_photo
        driver.save()

        return redirect('driverpages:homepage')

    return render(request, 'driverpages/settings.html', {
        'driver': driver
    })

