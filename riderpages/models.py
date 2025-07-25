# riderpages/models.py

from django.db import models
# Import the settings module to reference the AUTH_USER_MODEL
from django.conf import settings

# Choices for the Ride model fields
CAR_CHOICES = (
    ("sedan", "Sedan"),
    ("suv", "SUV"),
    ("bike", "Bike"),
    ("auto", "Auto"),
)

STATUS_CHOICES = (
    ("PENDING", "Pending"),
    ("CONFIRMED", "Confirmed"),
    ("IN_PROGRESS", "In Progress"),
    ("COMPLETED", "Completed"),
    ("CANCELLED", "Cancelled"),
)

class Ride(models.Model):
    """
    Represents a ride booking made by a user.
    """
    # CORRECTION:
    # Changed the foreign key to point to the user model defined in settings.py
    # This will now correctly point to your 'account.CustomUser' model.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='rides'
    )
    pickup_location = models.CharField(max_length=255)
    drop_location = models.CharField(max_length=255)
    car_type = models.CharField(max_length=10, choices=CAR_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # self.user will now correctly refer to your CustomUser object
        return f"Ride for {self.user} from {self.pickup_location} ({self.status})"

class ContactMessage(models.Model):
    """
    Stores messages submitted through the contact form.
    """
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.name} ({self.email})"