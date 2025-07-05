from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('driver', 'Driver'),
        ('rider', 'Rider'),
        ('admin', 'Admin'),
    ]
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name', 'role']

    def __str__(self):
        return f"{self.full_name} ({self.role})"
