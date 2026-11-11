from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from account.decorators import role_required
from turbo.maps import map_settings

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
            messages.success(request, "Ride booked! We're finding you a driver — you'll pay after the ride.")
            return redirect('riderpages:track_ride', ride_id=ride.id)

    return render(request, 'riderpages/map.html', {'base_fare': BASE_FARE, 'rates': RATE_PER_KM})


@rider_required
def booking_confirmation(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, user=request.user)

    if request.method == 'POST':
        was_pending = ride.status == 'PENDING'
        try:
            services.confirm_payment(ride, request.POST.get('payment_method'), request.POST.get('transaction_id'))
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            if was_pending:
                messages.success(request, "Your ride is confirmed. We're finding you a driver.")
            elif ride.payment_status == 'PAID':
                messages.success(request, "Payment received — thank you for riding with Turbo!")
            else:
                messages.success(request, "Please pay the driver in cash. They'll confirm once they've received it.")
            return redirect('riderpages:booking_confirmation', ride_id=ride.id)

    can_pay = ride.status == 'PENDING' or (ride.status == 'COMPLETED' and ride.payment_status == 'UNPAID')
    return render(request, 'riderpages/booking_confirmation.html',
                  {'ride': ride, 'upi_id': settings.UPI_ID, 'can_pay': can_pay})


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


@rider_required
def track_ride(request, ride_id):
    """Live tracking page for the rider's own ride (map, driver, OTP)."""
    from api.tracking_views import rider_tracking_data  # local import: api depends on this app

    ride = get_object_or_404(Ride.objects.select_related('driver__user'), id=ride_id, user=request.user)
    return render(request, 'riderpages/track.html', {
        'ride': ride,
        'trk_config': {
            'ride_id': ride.id,
            'login_url': reverse('account:rider_login'),
            'maps': map_settings(),
            'initial': rider_tracking_data(request, ride),
        },
    })
