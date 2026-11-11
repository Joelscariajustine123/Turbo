"""Driver rules shared by the website views and the REST API."""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Q, Sum
from django.utils import timezone

from account.services import check_email_free, validate_phone
from riderpages import otp
from riderpages.models import CAR_CHOICES, TRIP_STATUSES, Ride

from . import tracking
from .models import AvailabilityStatus, DriverLocation, DriverProfile, Earning, RideDecline


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
    return Ride.objects.select_related('user').filter(driver=driver, status__in=TRIP_STATUSES)


def ride_history(driver):
    return Ride.objects.select_related('user').filter(driver=driver).exclude(status__in=TRIP_STATUSES)


def accept_ride(driver, ride_id):
    if driver.availability_status == AvailabilityStatus.OFFLINE:
        raise ValidationError("You are offline. Set yourself to Available to accept rides.")
    with transaction.atomic():
        # Conditional UPDATE so two drivers can't both claim the same ride.
        now = timezone.now()
        claimed = Ride.objects.filter(
            id=ride_id, status='CONFIRMED', driver__isnull=True
        ).update(driver=driver, status='ACCEPTED', accepted_at=now, updated_at=now)
        if not claimed:
            raise ValidationError("This ride is no longer available.")
        DriverProfile.objects.filter(pk=driver.pk).update(availability_status=AvailabilityStatus.ON_TRIP)
        ride = Ride.objects.get(id=ride_id)
        otp.issue(ride)  # the rider can now see their pickup code
    return ride


def decline_ride(driver, ride_id):
    """Hide the ride from this driver only; other drivers can still accept it."""
    if not Ride.objects.filter(id=ride_id, status='CONFIRMED', driver__isnull=True).exists():
        raise ValidationError("This ride cannot be declined.")
    try:
        RideDecline.objects.get_or_create(driver=driver, ride_id=ride_id)
    except IntegrityError:
        pass


def _locked_ride(driver, ride_id):
    """The driver's own ride, row-locked. Other drivers' rides look like they don't exist."""
    ride = Ride.objects.select_for_update().filter(id=ride_id, driver=driver).first()
    if ride is None:
        raise ValidationError("Ride not found.")
    return ride


def mark_arrived(driver, ride_id):
    """ACCEPTED -> ARRIVED. Issues a fresh OTP so its validity starts now."""
    with transaction.atomic():
        ride = _locked_ride(driver, ride_id)
        if ride.status != 'ACCEPTED':
            raise ValidationError("You can only mark arrival while on the way to the pickup.")
        tracking.require_within(ride, 'pickup')
        ride.status = 'ARRIVED'
        ride.arrived_at = timezone.now()
        ride.save(update_fields=['status', 'arrived_at', 'updated_at'])
        otp.issue(ride)
    return ride


def verify_pickup_otp(driver, ride_id, code, ip_address=None):
    """ACCEPTED/ARRIVED -> IN_PROGRESS, only with the rider's valid code."""
    with transaction.atomic():
        ride = _locked_ride(driver, ride_id)
        if ride.otp_verified or ride.status == 'IN_PROGRESS':
            raise ValidationError("This ride has already started.")
        if ride.status == 'ACCEPTED':
            raise ValidationError("Tap \"Arrived\" when you reach the pickup (within "
                                  f"{tracking.geofence_radius_m()} m), then enter the rider's OTP.")
        if ride.status != 'ARRIVED':
            raise ValidationError("This ride can't be started.")
        result = otp.verify(ride, driver, code, ip_address)
        if result.ok:
            now = timezone.now()
            ride.status = 'IN_PROGRESS'
            ride.otp_verified = True
            ride.started_at = now
            ride.arrived_at = ride.arrived_at or now
            ride.save(update_fields=['status', 'otp_verified', 'started_at', 'arrived_at', 'updated_at'])
    # Raise outside the transaction so the failed-attempt counter is kept.
    if not result.ok:
        err = ValidationError(result.message, code=result.reason)
        err.attempts_left = result.attempts_left
        raise err
    return ride


def complete_ride(driver, ride_id):
    """IN_PROGRESS -> COMPLETED. Records the earning and stops location sharing."""
    with transaction.atomic():
        ride = Ride.objects.select_for_update().filter(id=ride_id, driver=driver).first()
        if ride is None or ride.status != 'IN_PROGRESS':
            raise ValidationError("A ride can only be completed after the passenger's OTP is verified.")
        tracking.require_within(ride, 'destination')
        ride.status = 'COMPLETED'
        ride.completed_at = timezone.now()
        ride.save(update_fields=['status', 'completed_at', 'updated_at'])
        Earning.objects.get_or_create(
            ride=ride,
            defaults={'driver': driver, 'amount': ride.fare or 0, 'date': timezone.localdate()},
        )
        DriverLocation.objects.filter(driver=driver, ride=ride).update(ride=None)
        if not Ride.objects.filter(driver=driver, status__in=TRIP_STATUSES).exists():
            DriverProfile.objects.filter(pk=driver.pk, availability_status=AvailabilityStatus.ON_TRIP) \
                .update(availability_status=AvailabilityStatus.AVAILABLE)
    return ride


def unpaid_rides(driver):
    """Completed rides whose fare hasn't been settled yet."""
    return (Ride.objects.select_related('user')
            .filter(driver=driver, status='COMPLETED').exclude(payment_status='PAID').order_by('-completed_at'))


def collect_cash(driver, ride_id):
    """Driver confirms the rider paid in cash after the ride."""
    with transaction.atomic():
        ride = _locked_ride(driver, ride_id)
        if ride.status != 'COMPLETED':
            raise ValidationError("Cash can be collected once the ride is completed.")
        if ride.payment_status == 'PAID':
            raise ValidationError("This ride is already paid.")
        ride.payment_method = 'CASH'
        ride.transaction_id = None
        ride.payment_status = 'PAID'
        ride.paid_at = timezone.now()
        ride.save(update_fields=['payment_method', 'transaction_id', 'payment_status', 'paid_at', 'updated_at'])
    return ride


# Allowed driver-initiated status changes. IN_PROGRESS is only reachable by OTP.
STATUS_ACTIONS = {
    'ARRIVED': mark_arrived,
    'COMPLETED': complete_ride,
}


def change_ride_status(driver, ride_id, status):
    status = (status or '').upper()
    if status == 'IN_PROGRESS':
        raise ValidationError("A ride starts only after the passenger's OTP is verified.")
    action = STATUS_ACTIONS.get(status)
    if action is None:
        raise ValidationError("Unsupported status change.")
    return action(driver, ride_id)


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
    if clean.get('availability_status') == AvailabilityStatus.OFFLINE and \
            Ride.objects.filter(driver=driver, status__in=TRIP_STATUSES).exists():
        errors.append("Finish your current ride before going offline — the rider is tracking you.")
    if clean.get('vehicle_type') and clean['vehicle_type'] not in dict(CAR_CHOICES):
        errors.append("Invalid vehicle type.")
    if 'vehicle_number' in clean:
        clean['vehicle_number'] = clean['vehicle_number'].upper()
    if errors:
        raise ValidationError(errors)

    user_fields = [f for f in ('full_name', 'phone', 'email') if f in clean]
    for f in user_fields:
        setattr(user, f, clean[f])
    if user_fields:
        user.save(update_fields=user_fields)

    for f in ('license_number', 'vehicle_info', 'vehicle_number', 'vehicle_type', 'availability_status'):
        if f in clean:
            setattr(driver, f, clean[f])
    if clean.get('availability_status') == AvailabilityStatus.OFFLINE:
        tracking.stop_sharing(driver)
    if photo:
        driver.profile_photo = photo
    driver.save()
    return driver
