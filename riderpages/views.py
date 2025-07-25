# riderpages/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Ride, ContactMessage
from django.contrib import messages # To show success messages

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

        # Create and save the contact message
        ContactMessage.objects.create(
            name=name,
            email=email,
            message=message_body
        )
        
        messages.success(request, 'Your message has been sent successfully!')
        return redirect('riderpages:contact') # Redirect back to the contact page

    return render(request, 'riderpages/contact.html')

@login_required # Ensures only logged-in users can book
def map_view(request):
    if request.method == 'POST':
        pickup_location = request.POST.get('pickup')
        drop_location = request.POST.get('drop')
        car_type = request.POST.get('car')

        # Create and save the ride booking
        Ride.objects.create(
            user=request.user,
            pickup_location=pickup_location,
            drop_location=drop_location,
            car_type=car_type,
            status='PENDING' # Default status
        )
        
        messages.success(request, 'Your ride has been booked! A driver will be assigned shortly.')
        return redirect('riderpages:index') # Redirect to the homepage after booking

    return render(request, 'riderpages/map.html')