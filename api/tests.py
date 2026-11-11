from django.core.cache import cache
from rest_framework.test import APITestCase

from account.models import CustomUser
from account.tests import PASSWORD, make_user
from driverpages.models import Earning, Rating
from riderpages import otp as otp_service
from riderpages.models import ContactMessage, Ride

COORDS = {'pickup_lat': 11.8745, 'pickup_lng': 75.3704, 'drop_lat': 11.95, 'drop_lng': 75.42}


class ApiTestCase(APITestCase):
    def setUp(self):
        cache.clear()  # reset login throttling between tests

    def login(self, email, role=None):
        body = {'email': email, 'password': PASSWORD}
        if role:
            body['role'] = role
        resp = self.client.post('/api/auth/login/', body, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        return resp.data


class AuthApiTests(ApiTestCase):
    def test_register_returns_tokens(self):
        resp = self.client.post('/api/auth/register/', {
            'role': 'driver', 'full_name': 'D', 'username': 'd1', 'email': 'd1@example.com',
            'password': PASSWORD, 'phone': '9876543210'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['user']['role'], 'driver')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        self.assertEqual(self.client.get('/api/driver/profile/').status_code, 200)

    def test_register_cannot_create_admin(self):
        resp = self.client.post('/api/auth/register/', {
            'role': 'admin', 'full_name': 'X', 'username': 'x', 'email': 'x@example.com',
            'password': PASSWORD}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('detail', resp.data)

    def test_register_errors_have_readable_detail(self):
        make_user('rider')
        resp = self.client.post('/api/auth/register/', {
            'role': 'rider', 'full_name': 'R', 'username': 'r2', 'email': 'rider@example.com',
            'password': PASSWORD}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists', resp.data['detail'])

    def test_login_role_mismatch_and_refresh_and_logout(self):
        make_user('rider')
        resp = self.client.post('/api/auth/login/', {'email': 'rider@example.com', 'password': PASSWORD,
                                                     'role': 'driver'}, format='json')
        self.assertEqual(resp.status_code, 401)
        tokens = self.login('rider@example.com', 'rider')
        resp = self.client.post('/api/auth/refresh/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(resp.status_code, 200)
        new_refresh = resp.data['refresh']
        self.assertEqual(self.client.post('/api/auth/logout/', {'refresh': new_refresh}, format='json').status_code, 205)
        resp = self.client.post('/api/auth/refresh/', {'refresh': new_refresh}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_me_and_change_password(self):
        make_user('rider')
        self.login('rider@example.com')
        resp = self.client.patch('/api/auth/me/', {'full_name': 'Renamed', 'role': 'admin'}, format='json')
        self.assertEqual((resp.data['full_name'], resp.data['role']), ('Renamed', 'rider'))
        resp = self.client.post('/api/auth/change-password/',
                                {'old_password': PASSWORD, 'new_password': 'Brand-new-pass-99'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_requires_auth_and_role(self):
        self.assertEqual(self.client.get('/api/rider/rides/').status_code, 401)
        make_user('rider')
        self.login('rider@example.com')
        self.assertEqual(self.client.get('/api/admin/stats/').status_code, 403)
        self.assertEqual(self.client.get('/api/driver/rides/available/').status_code, 403)

    def test_meta_and_contact_are_public(self):
        meta = self.client.get('/api/meta/').data
        self.assertEqual({c['value'] for c in meta['car_types']}, {'sedan', 'suv', 'bike', 'auto'})
        resp = self.client.post('/api/contact/', {'name': 'N', 'email': 'n@example.com', 'message': 'hi'},
                                format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(ContactMessage.objects.count(), 1)


class RideFlowApiTests(ApiTestCase):
    """Rider books -> pays -> driver accepts -> completes -> rider rates -> admin sees it."""

    def setUp(self):
        super().setUp()
        self.rider = make_user('rider')
        self.driver_user = make_user('driver', phone='9876543210')
        self.admin = make_user('admin')

    def test_full_flow(self):
        # Rider: quote, book, pay
        self.login('rider@example.com', 'rider')
        quote = self.client.post('/api/rider/quote/', COORDS, format='json').data
        self.assertEqual(set(quote['fares']), {'sedan', 'suv', 'bike', 'auto'})
        self.assertEqual(quote['source'], 'estimate')

        resp = self.client.post('/api/rider/rides/', {'pickup': 'Kannur', 'drop': 'Thalassery',
                                                      'car_type': 'suv', **COORDS}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ride_id = resp.data['id']
        self.assertEqual(resp.data['fare'], quote['fares']['suv'])
        self.assertTrue(resp.data['can_cancel'])

        resp = self.client.post(f'/api/rider/rides/{ride_id}/pay/', {'payment_method': 'upi'}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(f'/api/rider/rides/{ride_id}/pay/', {'payment_method': 'cash'}, format='json')
        self.assertEqual(resp.data['status'], 'CONFIRMED')

        # Driver: sees it without rider phone, accepts, then completes
        self.login('driver@example.com', 'driver')
        available = self.client.get('/api/driver/rides/available/').data['results']
        self.assertEqual([r['id'] for r in available], [ride_id])
        self.assertIsNone(available[0]['rider']['phone'])

        resp = self.client.post(f'/api/driver/rides/{ride_id}/accept/')
        self.assertEqual(resp.data['status'], 'ACCEPTED')
        self.assertEqual(self.client.get('/api/driver/profile/').data['availability_status'], 'on-trip')
        ongoing = self.client.get('/api/driver/rides/ongoing/').data['results']
        self.assertEqual(ongoing[0]['rider']['phone'], self.rider.phone)

        # A ride can't be completed until the passenger's OTP is verified.
        self.assertEqual(self.client.post(f'/api/driver/rides/{ride_id}/complete/').status_code, 400)
        code = otp_service.for_rider(Ride.objects.get(pk=ride_id)).code
        resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': ride_id, 'otp': code}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.client.post(f'/api/driver/rides/{ride_id}/complete/')
        self.assertEqual(resp.data['status'], 'COMPLETED')
        earnings = self.client.get('/api/driver/earnings/').data
        self.assertEqual(earnings['total_earnings'], quote['fares']['suv'])
        self.assertEqual(len(earnings['recent']), 1)

        # Rider: sees the driver, rates the ride once
        self.login('rider@example.com', 'rider')
        ride = self.client.get(f'/api/rider/rides/{ride_id}/').data
        self.assertEqual(ride['driver']['phone'], '9876543210')
        self.assertFalse(ride['can_cancel'])
        resp = self.client.post(f'/api/rider/rides/{ride_id}/rate/', {'rating': 5}, format='json')
        self.assertEqual(resp.data['rating'], 5)
        self.assertEqual(self.client.post(f'/api/rider/rides/{ride_id}/rate/', {'rating': 4},
                                          format='json').status_code, 400)
        self.assertEqual(Rating.objects.count(), 1)

        # Admin
        self.login('admin@example.com', 'admin')
        stats = self.client.get('/api/admin/stats/').data
        self.assertEqual((stats['total_bookings'], stats['total_riders'], stats['total_drivers']), (1, 1, 1))
        self.assertEqual(len(self.client.get('/api/admin/rides/?status=completed').data['results']), 1)
        self.assertEqual(len(self.client.get('/api/admin/rides/payments/').data['results']), 1)
        self.assertEqual(self.client.get('/api/admin/reports/').data[0]['completed_rides'], 1)

    def test_rider_cannot_touch_other_riders_ride(self):
        other = make_user('rider', email='other@example.com')
        ride = Ride.objects.create(user=other, pickup_location='A', drop_location='B', car_type='bike', fare=90)
        self.login('rider@example.com')
        self.assertEqual(self.client.get(f'/api/rider/rides/{ride.id}/').status_code, 404)
        self.assertEqual(self.client.post(f'/api/rider/rides/{ride.id}/cancel/').status_code, 404)

    def test_decline_is_per_driver_and_offline_driver_cannot_accept(self):
        ride = Ride.objects.create(user=self.rider, pickup_location='A', drop_location='B', car_type='bike',
                                   fare=90, status='CONFIRMED')
        self.login('driver@example.com')
        self.client.post(f'/api/driver/rides/{ride.id}/decline/')
        self.assertEqual(self.client.get('/api/driver/rides/available/').data['count'], 0)
        make_user('driver', email='d2@example.com')
        self.login('d2@example.com')
        self.assertEqual(self.client.get('/api/driver/rides/available/').data['count'], 1)
        self.client.patch('/api/driver/profile/', {'availability_status': 'offline'}, format='json')
        resp = self.client.post(f'/api/driver/rides/{ride.id}/accept/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('offline', resp.data['detail'])

    def test_driver_profile_update_validation(self):
        self.login('driver@example.com')
        resp = self.client.patch('/api/driver/profile/', {'phone': '12'}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.patch('/api/driver/profile/', {'vehicle_info': 'Swift KL13', 'license_number': 'L1'},
                                 format='json')
        self.assertEqual(resp.data['vehicle_info'], 'Swift KL13')


class AdminApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        make_user('admin')
        self.rider = make_user('rider')
        self.driver = make_user('driver')
        self.login('admin@example.com', 'admin')

    def test_manage_riders(self):
        self.assertEqual(self.client.get('/api/admin/riders/?search=rider').data['count'], 1)
        resp = self.client.patch(f'/api/admin/riders/{self.rider.id}/', {'is_active': False}, format='json')
        self.assertFalse(resp.data['is_active'])
        self.assertEqual(self.client.delete(f'/api/admin/riders/{self.rider.id}/').status_code, 204)
        self.assertFalse(CustomUser.objects.filter(pk=self.rider.pk).exists())

    def test_manage_drivers(self):
        resp = self.client.patch(f'/api/admin/drivers/{self.driver.id}/', {'availability_status': 'offline'},
                                 format='json')
        self.assertEqual(resp.data['availability_status'], 'offline')
        self.assertEqual(self.client.delete(f'/api/admin/drivers/{self.driver.id}/').status_code, 204)
        self.assertFalse(CustomUser.objects.filter(pk=self.driver.pk).exists())

    def test_create_admin(self):
        resp = self.client.post('/api/admin/admins/', {'full_name': 'A2', 'username': 'a2', 'email': 'a2@example.com',
                                                       'password': PASSWORD}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(CustomUser.objects.filter(role='admin').count(), 2)

    def test_earnings_without_ride_serialize(self):
        from driverpages.models import DriverProfile
        Earning.objects.create(driver=DriverProfile.objects.get(user=self.driver), amount=10, date='2026-01-01')
        self.login('driver@example.com')
        self.assertIsNone(self.client.get('/api/driver/earnings/').data['recent'][0]['pickup_location'])
