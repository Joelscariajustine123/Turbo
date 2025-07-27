from account.models import CustomUser
from django.shortcuts import get_object_or_404, redirect,render
from django.contrib import messages
from account.forms import EditRiderForm
from django.contrib.auth.decorators import login_required  
from riderpages.models import Ride 
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.db.models import Sum

# Create your views here.
@login_required
def home(request):
    # 1. Get total number of users with the 'rider' role
    total_riders = CustomUser.objects.filter(role='rider').count()

    # 2. Get total number of completed rides
    total_bookings = Ride.objects.filter(status='COMPLETED').count()

    # 3. Get total number of pending rides
    pending_requests = Ride.objects.filter(status='PENDING').count()

    # 4. Calculate revenue for the current month
    today = timezone.now()
    revenue_data = Ride.objects.filter(
        status='COMPLETED',
        created_at__year=today.year,
        created_at__month=today.month
    ).aggregate(total=Sum('fare'))
    
    # Get the sum, or default to 0 if there's no revenue
    monthly_revenue = revenue_data['total'] or 0

    context = {
        'total_riders': total_riders,
        'total_bookings': total_bookings,
        'pending_requests': pending_requests,
        'monthly_revenue': monthly_revenue,
    }
    return render(request, 'adminpages/home.html', context)
@login_required
def dashboard(request):
    # Fetch the 5 most recent rides by ordering by creation date descending
    recent_rides = Ride.objects.order_by('-created_at')[:5]
    
    context = {
        'recent_rides': recent_rides,
    }
    return render(request, 'adminpages/dashboard.html', context)
@login_required
def booking(request):
    # Fetch all Ride objects from the database, ordered by most recent
    all_rides = Ride.objects.all().order_by('-created_at')

    context = {
        'rides': all_rides,
        'ride_count': all_rides.count(), # Dynamic count of all rides
    }
    
    return render(request, 'adminpages/booking.html', context)
@login_required
def payment(request):
    # Fetch all rides where a fare exists, ordering by the most recent
    payments = Ride.objects.filter(fare__isnull=False).order_by('-created_at')
    
    context = {
        'payments': payments,
    }
    return render(request, 'adminpages/payment.html', context)
@login_required
def report(request):
    # This query groups rides by date and annotates each date
    # with calculated values.
    daily_reports = Ride.objects.annotate(
        date=TruncDate('created_at')  # Extract the date from the datetime field
    ).values('date').annotate(
        total_rides=Count('id'),
        completed_rides=Count('id', filter=Q(status='COMPLETED')),
        cancelled_rides=Count('id', filter=Q(status='CANCELLED')),
        total_revenue=Sum('fare', filter=Q(status='COMPLETED')),
        # Assumes a 'rating' reverse relationship from Ride to the Rating model
        avg_rating=Avg('rating__rating') 
    ).order_by('-date') # Order by most recent date

    context = {
        'reports': daily_reports
    }
    return render(request, 'adminpages/report.html', context)
@login_required
def rider(request):
    riders = CustomUser.objects.filter(role='rider')
    return render(request, 'adminpages/rider.html', {'riders': riders})

@login_required
def settings(request):
    user = request.user  # Get the currently logged-in user

    if request.method == 'POST':
        user.full_name = request.POST.get('name')
        user.email = request.POST.get('email')

        password = request.POST.get('password')
        if password:
            user.set_password(password)

        user.save()
        messages.success(request, "Account settings updated successfully.")
        return redirect('settings')  # Redirect to the same page

    return render(request, 'adminpages/settings.html', {
        'user': user
    })

@login_required
def delete_rider(request, rider_id):
    rider = get_object_or_404(CustomUser, id=rider_id, role='rider')
    if request.method == 'POST':
        rider.delete()
        messages.success(request, "Rider deleted successfully.")
    return redirect('rider')

@login_required
def edit_rider(request, rider_id):
    rider = get_object_or_404(CustomUser, id=rider_id, role='rider')
    if request.method == 'POST':
        form = EditRiderForm(request.POST, instance=rider)
        if form.is_valid():
            form.save()
            messages.success(request, "Rider updated successfully.")
            return redirect('adminpages:rider')
    else:
        form = EditRiderForm(instance=rider)
    return render(request, 'adminpages/edit_rider.html', {'form': form})