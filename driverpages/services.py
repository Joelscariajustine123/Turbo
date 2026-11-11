"""Driver rules shared by the website views and the REST API."""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Q, Sum
from django.utils import timezone

from account.services import check_email_free, validate_phone
from riderpages.models import Ride

from .models import AvailabilityStatus, DriverProfile, Earning, RideDecline


def get_driver(user):
    # get_or_create covers drivers created before the post_save signal existed.
    driver, _ = DriverProfile.objects.select_related('user').get_or_create(user=user)
    return driver


def available_rides(driver):
    return (Ride.objects.select_related('user')
            .filter(status='CONFIRMED', driver__isnull=True)
            .exclude(declines__driver=driver)
            .order_by('created_at'))


def ongoing_rides(driver):
    return Ride.objects.select_related('user').filter(driver=driver, status='ACCEPTED')


def ride_history(driver):
    return Ride.objects.select_related('user').filter(driver=driver).exclude(status='ACCEPTED')


def accept_ride(driver, ride_id):
    if driver.availability_status == AvailabilityStatus.OFFLINE:
        raise ValidationError("You are offline. Set yourself to Available to accept rides.")
    # Conditional UPDATE so two drivers can't both claim the same ride.
    claimed = Ride.objects.filter(
        id=ride_id, status='CONFIRMED', driver__isnull=True
    ).update(driver=driver, status='ACCEPTED', updated_at=timezone.now())
    if not claimed:
        raise ValidationError("This ride is no longer available.")
    DriverProfile.objects.filter(pk=driver.pk).update(availability_status=AvailabilityStatus.ON_TRIP)
    return Ride.objects.get(id=ride_id)


def decline_ride(driver, ride_id):
    """Hide the ride from this driver only; other drivers can still accept it."""
    if not Ride.objects.filter(id=ride_id, status='CONFIRMED', driver__isnull=True).exists():
        raise ValidationError("This ride cannot be declined.")
    try:
        RideDecline.objects.get_or_create(driver=driver, ride_id=ride_id)
    except IntegrityError:
        pass


def complete_ride(driver, ride_id):
    with transaction.atomic():
        ride = Ride.objects.select_for_update().filter(id=ride_id, driver=driver).first()
        if ride is None or ride.status != 'ACCEPTED':
            raise ValidationError("This ride cannot be marked as complete.")
        ride.status = 'COMPLETED'
        ride.save(update_fields=['status', 'updated_at'])
        Earning.objects.get_or_create(
            ride=ride,
            defaults={'driver': driver, 'amount': ride.fare or 0, 'date': timezone.localdate()},
        )
        if not Ride.objects.filter(driver=driver, status='ACCEPTED').exists():
            DriverProfile.objects.filter(pk=driver.pk, availability_status=AvailabilityStatus.ON_TRIP) \
                .update(availability_status=AvailabilityStatus.AVAILABLE)
    return ride


def earnings_summary(driver, days=30):
    today = timezone.localdate()
    qs = Earning.objects.filter(driver=driver)
    totals = qs.aggregate(
        total=Sum('amount'),
        daily=Sum('amount', filter=Q(date=today)),
        weekly=Sum('amount', filter=Q(date__gte=today - timedelta(days=6))),
        monthly=Sum('amount', filter=Q(date__gte=today - timedelta(days=29))),
    )
    per_day = (qs.filter(date__gte=today - timedelta(days=days - 1))
               .values('date').annotate(total=Sum('amount')).order_by('date'))
    return {
        'total_earnings': totals['total'] or 0,
        'daily_earnings': totals['daily'] or 0,
        'weekly_earnings': totals['weekly'] or 0,
        'monthly_earnings': totals['monthly'] or 0,
        'completed_rides': Ride.objects.filter(driver=driver, status='COMPLETED').count(),
        'average_rating': driver.ratings.aggregate(avg=Avg('rating'))['avg'],
        'chart': [{'date': row['date'], 'total': row['total']} for row in per_day],
    }


def update_profile(driver, data, photo=None):
    """Update a driver's account + profile. `data` may hold any subset of the fields."""
    user = driver.user
    clean = {k: str(v).strip() for k, v in data.items() if v is not None}
    if 'email' in clean:
        clean['email'] = clean['email'].lower()

    errors = []
    for key in ('full_name', 'phone', 'email', 'license_number', 'vehicle_info'):
        if key in clean and not clean[key]:
            errors.append(f"{key.replace('_', ' ').capitalize()} cannot be empty.")
    try:
        validate_phone(clean.get('phone', ''))
    except ValidationError as exc:
        errors.extend(exc.messages)
    if clean.get('email'):
        try:
            check_email_free(clean['email'], exclude_user=user)
        except ValidationError as exc:
            errors.extend(exc.messages)
    if 'availability_status' in clean and clean['availability_status'] not in AvailabilityStatus.values:
        errors.append("Invalid availability status.")
    if errors:
        raise ValidationError(errors)

    user_fields = [f for f in ('full_name', 'phone', 'email') if f in clean]
    for f in user_fields:
        setattr(user, f, clean[f])
    if user_fields:
        user.save(update_fields=user_fields)

    for f in ('license_number', 'vehicle_info', 'availability_status'):
        if f in clean:
            setattr(driver, f, clean[f])
    if photo:
        driver.profile_photo = photo
    driver.save()
    return driver
