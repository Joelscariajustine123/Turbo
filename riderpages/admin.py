# riderpages/admin.py

from django.contrib import admin
from .models import Ride, ContactMessage

@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ('user', 'pickup_location', 'drop_location', 'car_type', 'status', 'created_at')
    list_filter = ('status', 'car_type', 'created_at')
    search_fields = ('user__username', 'pickup_location', 'drop_location')
    list_per_page = 20

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at')
    search_fields = ('name', 'email', 'message')
    list_per_page = 20