"""Ride booking rules shared by the website views and the REST API."""
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from .models import PAYMENT_METHOD_CHOICES, ContactMessage, Ride
from .pricing import calculate_fare, get_route, parse_point

VALID_PAYMENT_METHODS = {code for code, _ in PAYMENT_METHOD_CHOICES}
CANCELLABLE_STATUSES = ('PENDING', 'CONFIRMED')


def quote(pickup_lat, pickup_lng, drop_lat, drop_lng):
    p = parse_point(pickup_lat, pickup_lng, "Pickup")
    d = parse_point(drop_lat, drop_lng, "Drop")
    return get_route(*p, *d)


def create_ride(user, *, pickup, drop, car_type, pickup_lat, pickup_lng, drop_lat, drop_lng):
    pickup = (pickup or '').strip()
    drop = (drop or '').strip()
    if not pickup or not drop:
        raise ValidationError("Please choose both a pickup and a drop location.")
    route = quote(pickup_lat, pickup_lng, drop_lat, drop_lng)
    fare = calculate_fare(car_type, route.distance_km)
    return Ride.objects.create(
        user=user,
        pickup_location=pickup[:255], drop_location=drop[:255],
        pickup_lat=round(float(pickup_lat), 6), pickup_lng=round(float(pickup_lng), 6),
        drop_lat=round(float(drop_lat), 6), drop_lng=round(float(drop_lng), 6),
        car_type=car_type, distance=route.distance_km, fare=fare, status='PENDING',
    )


def confirm_payment(ride, payment_method, transaction_id=''):
    payment_method = (payment_method or '').upper()
    transaction_id = (transaction_id or '').strip()
    if ride.status != 'PENDING':
        raise ValidationError("This ride has already been confirmed.")
    if payment_method not in VALID_PAYMENT_METHODS:
        raise ValidationError("Please select a payment method.")
    if payment_method == 'UPI' and not transaction_id:
        raise ValidationError("Please enter the UPI transaction ID.")

    ride.payment_method = payment_method
    ride.transaction_id = transaction_id[:100] if payment_method == 'UPI' else None
    ride.status = 'CONFIRMED'
    ride.save(update_fields=['payment_method', 'transaction_id', 'status', 'updated_at'])
    return ride


def cancel_ride(ride):
    with transaction.atomic():
        updated = Ride.objects.filter(pk=ride.pk, status__in=CANCELLABLE_STATUSES).update(status='CANCELLED')
    if not updated:
        raise ValidationError("This ride can no longer be cancelled.")
    ride.refresh_from_db()
    return ride


def rate_ride(ride, rating, review_text=''):
    from driverpages.models import Rating  # local import: driverpages imports riderpages

    if ride.status != 'COMPLETED' or ride.driver_id is None:
        raise ValidationError("You can only rate a completed ride.")
    try:
        rating = float(rating)
    except (TypeError, ValueError):
        raise ValidationError("Rating must be a number from 1 to 5.")
    if not 1 <= rating <= 5:
        raise ValidationError("Rating must be a number from 1 to 5.")
    if Rating.objects.filter(ride=ride).exists():
        raise ValidationError("You have already rated this ride.")
    return Rating.objects.create(driver_id=ride.driver_id, ride=ride, rating=rating,
                                 review_text=(review_text or '').strip())


def save_contact_message(name, email, message_body):
    name, email, message_body = (name or '').strip(), (email or '').strip(), (message_body or '').strip()
    if not (name and email and message_body):
        raise ValidationError("All fields are required.")
    validate_email(email)
    return ContactMessage.objects.create(name=name[:100], email=email, message=message_body)
