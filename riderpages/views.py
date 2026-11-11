from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from account.decorators import role_required

from . import services
from .models import BASE_FARE, RATE_PER_KM, Ride

rider_required = role_required('rider')


VEHICLES = [
    {'value': 'bike', 'label': 'Bike', 'seats': '1 rider', 'icon': 'bx-cycling',
     'blurb': 'Beat the traffic on short city hops.'},
    {'value': 'auto', 'label': 'Auto', 'seats': 'Up to 3', 'icon': 'bxs-taxi',
     'blurb': 'Affordable everyday rides around town.'},
    {'value': 'sedan', 'label': 'Sedan', 'seats': 'Up to 4', 'img': 'sedan',
     'blurb': 'Comfortable, air-conditioned and quiet.'},
    {'value': 'suv', 'label': 'SUV', 'seats': 'Up to 6', 'img': 'suv',
     'blurb': 'Extra room for family and luggage.'},
]


def index(request):
    vehicles = [{**v, 'rate': RATE_PER_KM[v['value']]} for v in VEHICLES]
    return render(request, 'riderpages/index.html', {
        'vehicles': vehicles,
        'base_fare': BASE_FARE,
        'min_rate': min(RATE_PER_KM.values()),
    })


def safety(request):
    return render(request, 'riderpages/Safety.html')


POPULAR_ROUTES = [
    ('Bangalore', 'Mysore'),
    ('Delhi', 'Agra'),
    ('Mumbai', 'Lonavala'),
    ('Chennai', 'Pondicherry'),
    ('Hyderabad', 'Warangal'),
]


def outstation(request):
    return render(request, 'riderpages/outstation.html', {'routes': POPULAR_ROUTES})


def services_page(request):
    return render(request, 'riderpages/services.html')


def contact(request):
    if request.method == 'POST':
        try:
            services.save_contact_message(request.POST.get('name'), request.POST.get('email'), request.POST.get('message'))
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return render(request, 'riderpages/contact.html', {'form_data': request.POST})
        messages.success(request, 'Your message has been sent successfully!')
        return redirect('riderpages:contact')
    return render(request, 'riderpages/contact.html')


@rider_required
def map_view(request):
    if request.method == 'POST':
        p = request.POST
        try:
            ride = services.create_ride(
                request.user,
                pickup=p.get('pickup'), drop=p.get('drop'), car_type=p.get('car', ''),
                pickup_lat=p.get('pickup_lat'), pickup_lng=p.get('pickup_lng'),
                drop_lat=p.get('drop_lat'), drop_lng=p.get('drop_lng'),
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            return redirect('riderpages:booking_confirmation', ride_id=ride.id)

    return render(request, 'riderpages/map.html', {'base_fare': BASE_FARE, 'rates': RATE_PER_KM})


@rider_required
def booking_confirmation(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, user=request.user)

    if request.method == 'POST':
        try:
            services.confirm_payment(ride, request.POST.get('payment_method'), request.POST.get('transaction_id'))
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            if ride.status != 'PENDING':
                return redirect('riderpages:my_rides')
        else:
            messages.success(
                request,
                f"Your ride has been confirmed! Payment method: {ride.get_payment_method_display()}. "
                "A driver will be assigned shortly.",
            )
            return redirect('riderpages:my_rides')

    return render(request, 'riderpages/booking_confirmation.html', {'ride': ride, 'upi_id': settings.UPI_ID})


@rider_required
def my_rides(request):
    rides = Ride.objects.select_related('driver__user').filter(user=request.user)
    return render(request, 'riderpages/my_rides.html', {'rides': rides})


@rider_required
@require_POST
def cancel_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, user=request.user)
    try:
        services.cancel_ride(ride)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.info(request, "Your ride has been cancelled.")
    return redirect('riderpages:my_rides')
