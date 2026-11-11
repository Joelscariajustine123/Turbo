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
    phone = models.CharField(max_length=10, default="9999999999")
    # Set once the user enters the code emailed at registration (see account/email_otp.py).
    email_verified = models.BooleanField(default=False)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name', 'role']

    def __str__(self):
        return f"{self.full_name} ({self.role})"


class EmailOTP(models.Model):
    """A 6-digit code emailed to confirm registration or a login. Only a keyed hash is stored."""
    PURPOSES = [('register', 'Registration'), ('login', 'Login')]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_otps')
    purpose = models.CharField(max_length=10, choices=PURPOSES)
    code_hash = models.CharField(max_length=64)
    sent_to = models.EmailField()
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'purpose', 'created_at'])]

    def __str__(self):
        return f"{self.purpose} code for {self.sent_to}"
