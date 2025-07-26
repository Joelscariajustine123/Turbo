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

class Ride(models.Model):
    # Rider-related fields
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='rides_as_rider'
    )
    pickup_location = models.CharField(max_length=255)
    drop_location = models.CharField(max_length=255)
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
    
    # Status and Timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Ride from {self.pickup_location} for {self.user.full_name}"

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.name} ({self.email})"
