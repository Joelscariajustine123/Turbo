from django.db import models
from django.conf import settings

# Helper for driver availability
class AvailabilityStatus(models.TextChoices):
    AVAILABLE = 'available', 'Available'
    OFFLINE = 'offline', 'Offline'
    ON_TRIP = 'on-trip', 'On a Trip'

class DriverProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    license_number = models.CharField(max_length=20)
    vehicle_info = models.CharField(max_length=100)
    availability_status = models.CharField(max_length=10, choices=AvailabilityStatus.choices, default=AvailabilityStatus.AVAILABLE)
    profile_photo = models.ImageField(upload_to='driver_photos/', blank=True, null=True)

    def __str__(self):
        return self.user.full_name

class Ride(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='rides')
    pickup_location = models.CharField(max_length=100)
    drop_location = models.CharField(max_length=100)
    is_completed = models.BooleanField(default=False)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.pickup_location} to {self.drop_location}"

class Earning(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='earnings')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    date = models.DateField()

    def __str__(self):
        return f"{self.driver.user.full_name} - ${self.amount} on {self.date}"

class Rating(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='ratings')
    rating = models.FloatField()
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.driver.user.full_name} - {self.rating}"
