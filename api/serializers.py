from rest_framework import serializers

from account.models import CustomUser
from driverpages.models import DriverProfile, Earning
from riderpages.models import ContactMessage, Ride


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'full_name', 'phone', 'role', 'is_active', 'email_verified', 'date_joined']
        read_only_fields = ['id', 'username', 'role', 'is_active', 'email_verified', 'date_joined']

    def validate_email(self, value):
        value = value.strip().lower()
        qs = CustomUser.objects.filter(email__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if value and (not value.isdigit() or len(value) != 10):
            raise serializers.ValidationError("Phone number must be exactly 10 digits.")
        return value


class AdminUserSerializer(UserSerializer):
    """Admins may also activate / deactivate accounts."""
    class Meta(UserSerializer.Meta):
        read_only_fields = ['id', 'username', 'role', 'email_verified', 'date_joined']


class RegisterSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['rider', 'driver'])
    full_name = serializers.CharField(max_length=100)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=10, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['rider', 'driver', 'admin'], required=False)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField()


class DriverProfileSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id', read_only=True)
    profile_id = serializers.IntegerField(source='id', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    availability_display = serializers.CharField(source='get_availability_status_display', read_only=True)

    class Meta:
        model = DriverProfile
        fields = ['id', 'profile_id', 'username', 'full_name', 'email', 'phone', 'is_active', 'date_joined',
                  'license_number', 'vehicle_info', 'vehicle_number', 'vehicle_type', 'availability_status',
                  'availability_display', 'profile_photo']
        read_only_fields = fields


class _PersonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    phone = serializers.CharField()


class RideSerializer(serializers.ModelSerializer):
    car_type_display = serializers.CharField(source='get_car_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    needs_payment = serializers.SerializerMethodField()
    rider = serializers.SerializerMethodField()
    driver = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Ride
        fields = ['id', 'pickup_location', 'drop_location', 'pickup_lat', 'pickup_lng', 'drop_lat', 'drop_lng',
                  'car_type', 'car_type_display', 'distance', 'fare', 'status', 'status_display',
                  'payment_method', 'payment_method_display', 'transaction_id', 'otp_verified',
                  'payment_status', 'payment_status_display', 'needs_payment', 'paid_at',
                  'accepted_at', 'arrived_at', 'started_at', 'completed_at',
                  'created_at', 'updated_at', 'rider', 'driver', 'rating', 'can_cancel']
        read_only_fields = fields

    def _show_contact(self, ride):
        # Phone numbers are only shared once a driver has taken the ride (admins see everything).
        if self.context.get('show_all'):
            return True
        return not self.context.get('hide_contact') and ride.driver_id is not None

    def get_rider(self, ride):
        u = ride.user
        return {'id': u.id, 'full_name': u.full_name, 'phone': u.phone if self._show_contact(ride) else None}

    def get_driver(self, ride):
        d = ride.driver
        if d is None:
            return None
        request = self.context.get('request')
        photo = d.profile_photo.url if d.profile_photo else None
        if photo and request is not None:
            photo = request.build_absolute_uri(photo)
        return {'id': d.user_id, 'full_name': d.user.full_name, 'phone': d.user.phone,
                'vehicle_info': d.vehicle_info, 'vehicle_number': d.vehicle_number,
                'vehicle_type': d.get_vehicle_type_display() if d.vehicle_type else '',
                'profile_photo': photo}

    def get_rating(self, ride):
        ratings = list(ride.rating_set.all())  # uses prefetch_related('rating_set')
        return ratings[0].rating if ratings else None

    def get_needs_payment(self, ride):
        return ride.status == 'COMPLETED' and ride.payment_status == 'UNPAID'

    def get_can_cancel(self, ride):
        return ride.status in ('PENDING', 'CONFIRMED')


class RideCreateSerializer(serializers.Serializer):
    pickup = serializers.CharField(max_length=255)
    drop = serializers.CharField(max_length=255)
    car_type = serializers.CharField()
    pickup_lat = serializers.FloatField()
    pickup_lng = serializers.FloatField()
    drop_lat = serializers.FloatField()
    drop_lng = serializers.FloatField()


class QuoteSerializer(serializers.Serializer):
    pickup_lat = serializers.FloatField()
    pickup_lng = serializers.FloatField()
    drop_lat = serializers.FloatField()
    drop_lng = serializers.FloatField()


class PaymentSerializer(serializers.Serializer):
    payment_method = serializers.CharField()
    transaction_id = serializers.CharField(required=False, allow_blank=True, default='')


class RatingSerializer(serializers.Serializer):
    rating = serializers.FloatField(min_value=1, max_value=5)
    review_text = serializers.CharField(required=False, allow_blank=True, default='')


class EarningSerializer(serializers.ModelSerializer):
    pickup_location = serializers.CharField(source='ride.pickup_location', default=None, read_only=True)
    drop_location = serializers.CharField(source='ride.drop_location', default=None, read_only=True)
    rider_name = serializers.CharField(source='ride.user.full_name', default=None, read_only=True)

    class Meta:
        model = Earning
        fields = ['id', 'amount', 'date', 'ride', 'pickup_location', 'drop_location', 'rider_name']


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']


class LocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    accuracy = serializers.FloatField(min_value=0, max_value=100000, required=False, allow_null=True)
    speed = serializers.FloatField(min_value=0, max_value=400, required=False, allow_null=True)   # km/h
    heading = serializers.FloatField(min_value=0, max_value=360, required=False, allow_null=True)


class RideStatusSerializer(serializers.Serializer):
    ride_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=['ARRIVED', 'IN_PROGRESS', 'COMPLETED'])


class VerifyOTPSerializer(serializers.Serializer):
    ride_id = serializers.IntegerField()
    otp = serializers.RegexField(r'^\s*\d{6}\s*$', error_messages={'invalid': 'Enter the 6-digit code.'})
