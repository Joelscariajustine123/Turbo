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

STATUS_CHOICES = (
    ("PENDING", "Pending"),       # Rider has not paid yet
    ("CONFIRMED", "Confirmed"),   # Paid, waiting for a driver
    ("ACCEPTED", "Accepted"),     # Driver has accepted the ride
    ("IN_PROGRESS", "In Progress"), # Ride is ongoing
    ("COMPLETED", "Completed"),   # Ride finished
    ("CANCELLED", "Cancelled"),   # Ride cancelled
)
PAYMENT_METHOD_CHOICES = (
    ("UPI", "UPI"),
    ("CASH", "Cash"),
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
    # Status and Timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Ride from {self.pickup_location} for {self.user.full_name}"

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Message from {self.name} ({self.email})"
