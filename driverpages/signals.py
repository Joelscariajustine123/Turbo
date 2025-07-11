from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import DriverProfile

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_driver_profile(sender, instance, created, **kwargs):
    if created and instance.role == 'driver':
        DriverProfile.objects.create(user=instance)
