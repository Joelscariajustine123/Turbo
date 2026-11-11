# driverpages/models.py
from django.conf import settings
from django.db import models

from riderpages.models import CAR_CHOICES

class AvailabilityStatus(models.TextChoices):
    AVAILABLE = 'available', 'Available'
    OFFLINE = 'offline', 'Offline'
    ON_TRIP = 'on-trip', 'On a Trip'

class DriverProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    license_number = models.CharField(max_length=20)
    vehicle_info = models.CharField(max_length=100)  # shown as "vehicle model"
    vehicle_number = models.CharField(max_length=20, blank=True)  # registration plate
    vehicle_type = models.CharField(max_length=10, choices=CAR_CHOICES, blank=True)
    availability_status = models.CharField(max_length=10, choices=AvailabilityStatus.choices, default=AvailabilityStatus.AVAILABLE)
    profile_photo = models.ImageField(upload_to='driver_photos/', blank=True, null=True)

    def __str__(self):
        return self.user.full_name

class Earning(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='earnings')
    # Link to the Ride model using a string to avoid circular imports
    ride = models.OneToOneField('riderpages.Ride', on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    date = models.DateField()

    def __str__(self):
        return f"{self.driver.user.full_name} - ₹{self.amount} on {self.date}"

class RideDecline(models.Model):
    """A driver said no to a ride: hide it from that driver only (others can still accept it)."""
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='declined')
    ride = models.ForeignKey('riderpages.Ride', on_delete=models.CASCADE, related_name='declines')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['driver', 'ride'], name='unique_driver_ride_decline')]

    def __str__(self):
        return f"{self.driver} declined ride {self.ride_id}"


class Rating(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='ratings')
    # Link to the Ride model using a string to avoid circular imports
    ride = models.ForeignKey('riderpages.Ride', on_delete=models.SET_NULL, null=True, blank=True)
    rating = models.FloatField()
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.driver.user.full_name} - {self.rating}"


class DriverLocation(models.Model):
    """The driver's latest GPS fix (one row per driver, overwritten every few seconds)."""
    driver = models.OneToOneField(DriverProfile, on_delete=models.CASCADE, related_name='location')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy = models.FloatField(null=True, blank=True)   # metres
    speed = models.FloatField(null=True, blank=True)      # km/h
    heading = models.FloatField(null=True, blank=True)    # degrees from north
    is_online = models.BooleanField(default=True)
    ride = models.ForeignKey('riderpages.Ride', on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='driver_locations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        return f"{self.driver} @ {self.latitude},{self.longitude}"


class TripLocationPoint(models.Model):
    """Sparse breadcrumb trail of an active ride (kept for TURBO_TRACK_RETENTION_DAYS)."""
    ride = models.ForeignKey('riderpages.Ride', on_delete=models.CASCADE, related_name='track_points')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['ride', 'recorded_at']), models.Index(fields=['recorded_at'])]
