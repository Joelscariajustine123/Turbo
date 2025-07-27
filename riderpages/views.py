# riderpages/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Ride, ContactMessage
from django.contrib import messages

def index(request):
    return render(request, 'riderpages/index.html')

def safety(request):
    return render(request, 'riderpages/Safety.html')

def outstation(request):
    return render(request, 'riderpages/outstation.html')

def services(request):
    return render(request, 'riderpages/services.html')

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message_body = request.POST.get('message')
        ContactMessage.objects.create(name=name, email=email, message=message_body)
        messages.success(request, 'Your message has been sent successfully!')
        return redirect('riderpages:contact')
    return render(request, 'riderpages/contact.html')

@login_required
def map_view(request):
    # This view now handles both displaying the map and creating the ride
    if request.method == 'POST':
        # Create a ride instance but don't finalize it yet
        ride = Ride.objects.create(
            user=request.user,
            pickup_location=request.POST.get('pickup'),
            drop_location=request.POST.get('drop'),
            car_type=request.POST.get('car'),
            distance=request.POST.get('distance'),
            fare=request.POST.get('fare'),
            status='PENDING' # The ride is pending until payment
        )
        # Redirect to the new confirmation page with the ride's ID
        return redirect('riderpages:booking_confirmation', ride_id=ride.id)

    # For GET requests, just show the map page
    return render(request, 'riderpages/map.html')
@login_required
def booking_confirmation(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, user=request.user)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        transaction_id = request.POST.get('transaction_id') # Get the transaction ID

        # --- FIX: Save the payment details to the ride object ---
        if payment_method:
            ride.payment_method = payment_method.upper() # e.g., 'CASH' or 'UPI'
            ride.status = 'CONFIRMED'
            
            # Save the transaction ID only if the method is UPI
            if payment_method == 'upi' and transaction_id:
                ride.transaction_id = transaction_id

            ride.save() # Save all the changes
            
            messages.success(request, f"Your ride has been confirmed! Payment method: {payment_method.title()}. A driver will be assigned shortly.")
            return redirect('riderpages:index')
        else:
            # Handle case where payment method is not provided
            messages.error(request, 'Please select a payment method.')

    context = {'ride': ride}
    return render(request, 'riderpages/booking_confirmation.html', context)