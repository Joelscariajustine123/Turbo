# riderpages/models.py
from django.db import models
from django.conf import settings

# CHOICES
CAR_CHOICES = (
    ("sedan", "Sedan"),
    ("suv", "SUV"),
    ("bike", "Bike"),
    ("auto", "Auto"),
)

# Ride lifecycle. A ride can only move forward through these steps
# (see driverpages.services):
#   PENDING -> CONFIRMED -> ACCEPTED -> ARRIVED -> IN_PROGRESS -> COMPLETED
# ACCEPTED    = driver assigned and on the way to pickup (OTP issued to the rider)
# ARRIVED     = driver at pickup, waiting for the rider's OTP
# IN_PROGRESS = OTP verified, ride started, on the way to the destination
STATUS_CHOICES = (
    ("PENDING", "Pending"),                # Rider has not paid yet
    ("CONFIRMED", "Confirmed"),            # Paid, waiting for a driver
    ("ACCEPTED", "Driver Assigned"),       # Driver on the way to pickup
    ("ARRIVED", "Driver Arrived"),         # Driver at pickup, OTP pending
    ("IN_PROGRESS", "Ride Started"),       # OTP verified, heading to destination
    ("COMPLETED", "Completed"),            # Ride finished
    ("CANCELLED", "Cancelled"),            # Ride cancelled
)
# Statuses during which the assigned driver's live location is shared with the rider.
TRIP_STATUSES = ("ACCEPTED", "ARRIVED", "IN_PROGRESS")
ACTIVE_STATUSES = ("PENDING", "CONFIRMED") + TRIP_STATUSES
PAYMENT_METHOD_CHOICES = (
    ("UPI", "UPI"),
    ("CASH", "Cash"),
)
# The rider pays after the ride is completed (like Uber):
#   UNPAID -> PAID (UPI with transaction id)
#   UNPAID -> CASH_DUE (rider chose cash) -> PAID (driver confirms cash collected)
PAYMENT_STATUS_CHOICES = (
    ("UNPAID", "Unpaid"),
    ("CASH_DUE", "Cash due"),
    ("PAID", "Paid"),
)

# Fare = BASE_FARE + distance_km * rate. Kept server-side so the price can't be
# edited in the browser; map.html shows the same numbers for the estimate.
BASE_FARE = 50
RATE_PER_KM = {
    "sedan": 15,
    "suv": 20,
    "bike": 8,
    "auto": 12,
}
class Ride(models.Model):
    # Rider-related fields
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='rides_as_rider'
    )
    pickup_location = models.CharField(max_length=255)
    drop_location = models.CharField(max_length=255)
    # Coordinates let the server work out the distance itself (see pricing.py).
    pickup_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    drop_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    drop_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    car_type = models.CharField(max_length=10, choices=CAR_CHOICES)
    distance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fare = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)

    # Driver-related fields are linked using a string to avoid circular imports
    driver = models.ForeignKey(
        'driverpages.DriverProfile', 
        on_delete=models.SET_NULL,
        related_name='rides_as_driver',
        null=True, 
        blank=True
    )
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHOD_CHOICES, 
        null=True, 
        blank=True
    )
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='UNPAID', db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    # Status and Timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    otp_verified = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['driver', 'status']), models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f"Ride from {self.pickup_location} for {self.user.full_name}"

    @property
    def is_trip_active(self):
        return self.status in TRIP_STATUSES


class RideOTP(models.Model):
    """Pickup verification code for one ride (see riderpages/otp.py).

    No plaintext is stored: the rider's code is derived from `nonce` with the
    server's SECRET_KEY, and `otp_hash` is what the driver's entry is checked against.
    """
    ride = models.OneToOneField(Ride, on_delete=models.CASCADE, related_name='otp')
    nonce = models.CharField(max_length=64)
    otp_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    regenerated_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField()

    def __str__(self):
        return f"OTP for ride {self.ride_id} ({'verified' if self.is_verified else 'pending'})"


class OTPAttempt(models.Model):
    """Audit log of every OTP verification attempt."""
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name='otp_attempts')
    driver = models.ForeignKey('driverpages.DriverProfile', on_delete=models.SET_NULL, null=True, blank=True)
    success = models.BooleanField(default=False)
    reason = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Ride {self.ride_id}: {'ok' if self.success else self.reason}"

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Message from {self.name} ({self.email})"
