"""Live tracking + pickup OTP: access rules, OTP security, status workflow."""
import json
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from account.tests import PASSWORD, make_user
from driverpages.models import DriverLocation, DriverProfile, TripLocationPoint
from riderpages import otp as otp_service
from riderpages.models import OTPAttempt, Ride, RideOTP

KANNUR = {'pickup_lat': 11.8745, 'pickup_lng': 75.3704, 'drop_lat': 11.95, 'drop_lng': 75.42}
NEAR_PICKUP = {'latitude': 11.8800, 'longitude': 75.3650, 'accuracy': 8, 'speed': 22, 'heading': 135}


class TrackingTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.rider = make_user('rider')
        self.other_rider = make_user('rider', email='other.rider@example.com')
        self.driver_user = make_user('driver', phone='9876543210')
        self.other_driver_user = make_user('driver', email='other.driver@example.com')
        self.driver = DriverProfile.objects.get(user=self.driver_user)
        DriverProfile.objects.filter(pk=self.driver.pk).update(vehicle_info='Swift Dzire', vehicle_number='KL13AB1234',
                                                               vehicle_type='sedan')
        self.ride = Ride.objects.create(user=self.rider, pickup_location='Kannur', drop_location='Thalassery',
                                        car_type='sedan', distance=12, fare=230, status='CONFIRMED',
                                        payment_method='CASH', **KANNUR)

    def as_user(self, user):
        self.client.force_authenticate(user)

    def accept(self):
        self.as_user(self.driver_user)
        resp = self.client.post(f'/api/driver/rides/{self.ride.id}/accept/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.ride.refresh_from_db()

    def code(self):
        return otp_service.for_rider(Ride.objects.get(pk=self.ride.pk)).code

    def send_location(self, **overrides):
        self.as_user(self.driver_user)
        return self.client.post('/api/driver/location/update/', {**NEAR_PICKUP, **overrides}, format='json')


class DriverLocationTests(TrackingTestCase):
    def test_update_and_read_current_location(self):
        resp = self.send_location()
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['driver_status']['key'], 'online')
        self.assertIsNone(resp.data['tracking'])
        cur = self.client.get('/api/driver/location/current/').data
        self.assertAlmostEqual(cur['location']['lat'], 11.88)
        self.assertEqual(DriverLocation.objects.count(), 1)

    def test_repeated_updates_overwrite_a_single_row(self):
        for i in range(5):
            self.send_location(latitude=11.88 + i * 0.001)
        self.assertEqual(DriverLocation.objects.count(), 1)

    def test_invalid_coordinates_rejected(self):
        self.assertEqual(self.send_location(latitude=123).status_code, 400)
        self.assertEqual(self.send_location(longitude='abc').status_code, 400)
        self.assertEqual(self.send_location(latitude=0, longitude=0).status_code, 409)

    def test_offline_driver_cannot_share_location(self):
        DriverProfile.objects.filter(pk=self.driver.pk).update(availability_status='offline')
        resp = self.send_location()
        self.assertEqual(resp.status_code, 409)
        self.assertFalse(resp.data['tracking_allowed'])

    def test_unauthenticated_and_wrong_role_rejected(self):
        self.assertEqual(self.client.post('/api/driver/location/update/', NEAR_PICKUP, format='json').status_code, 401)
        self.as_user(self.rider)
        self.assertEqual(self.client.post('/api/driver/location/update/', NEAR_PICKUP, format='json').status_code, 403)
        self.assertEqual(self.client.get('/api/driver/active-ride/').status_code, 403)

    def test_cannot_go_offline_during_trip_and_offline_stops_sharing(self):
        self.accept()
        self.send_location()
        resp = self.client.patch('/api/driver/profile/', {'availability_status': 'offline'}, format='json')
        self.assertEqual(resp.status_code, 400)
        # With no trip, going offline hides the position.
        Ride.objects.filter(pk=self.ride.pk).update(status='CANCELLED')
        self.client.patch('/api/driver/profile/', {'availability_status': 'offline'}, format='json')
        self.assertFalse(DriverLocation.objects.get().is_online)

    def test_breadcrumbs_are_sparse(self):
        self.accept()
        for _ in range(5):
            self.send_location()  # same spot, within seconds
        self.assertEqual(TripLocationPoint.objects.filter(ride=self.ride).count(), 1)


class RiderTrackingTests(TrackingTestCase):
    def test_rider_sees_assigned_driver_live_with_route_and_eta(self):
        self.as_user(self.rider)
        before = self.client.get('/api/rider/ride/tracking/').data
        self.assertEqual(before['status'], 'CONFIRMED')
        self.assertIsNone(before['driver_location'])
        self.assertEqual(self.client.get('/api/rider/ride/driver-location/').status_code, 404)

        self.accept()
        self.send_location()
        self.as_user(self.rider)
        data = self.client.get('/api/rider/ride/tracking/').data
        self.assertTrue(data['tracking_active'])
        self.assertAlmostEqual(data['driver_location']['lat'], 11.88)
        self.assertEqual(data['stage'], 'pickup')
        self.assertGreater(data['distance_to_pickup_km'], 0)
        self.assertGreater(data['distance_to_destination_km'], data['distance_to_pickup_km'])
        self.assertGreaterEqual(data['eta_minutes'], 1)
        self.assertGreaterEqual(len(data['route']['geometry']), 2)
        self.assertEqual(data['driver']['vehicle_number'], 'KL13AB1234')
        self.assertEqual(data['driver']['vehicle_type'], 'Sedan')
        self.assertEqual(data['driver']['phone'], '9876543210')

        loc = self.client.get('/api/rider/ride/driver-location/').data
        self.assertAlmostEqual(loc['location']['lng'], 75.365)
        active = self.client.get('/api/rider/ride/active/').data
        self.assertEqual(active['ride']['id'], self.ride.id)

    def test_other_rider_cannot_see_driver_or_ride(self):
        self.accept()
        self.send_location()
        self.as_user(self.other_rider)
        self.assertEqual(self.client.get(f'/api/rider/ride/tracking/?ride_id={self.ride.id}').status_code, 404)
        self.assertEqual(self.client.get(f'/api/rider/ride/driver-location/?ride_id={self.ride.id}').status_code, 404)
        self.assertEqual(self.client.get(f'/api/rider/ride/otp/?ride_id={self.ride.id}').status_code, 404)
        self.assertEqual(self.client.get('/api/rider/ride/tracking/').status_code, 404)  # no active ride of their own

    def test_tracking_stops_after_completion(self):
        self.accept()
        self.send_location()
        self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': self.code()}, format='json')
        self.client.post('/api/driver/ride/status/', {'ride_id': self.ride.id, 'status': 'COMPLETED'}, format='json')
        self.as_user(self.rider)
        data = self.client.get(f'/api/rider/ride/tracking/?ride_id={self.ride.id}').data
        self.assertEqual(data['status'], 'COMPLETED')
        self.assertIsNone(data['driver_location'])
        self.assertFalse(data['tracking_active'])
        self.assertEqual(self.client.get(f'/api/rider/ride/driver-location/?ride_id={self.ride.id}').status_code, 404)
        self.assertIsNone(DriverLocation.objects.get().ride)

    def test_destination_stage_after_otp(self):
        self.accept()
        self.send_location()
        resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': self.code()},
                                format='json')
        self.assertEqual(resp.data['tracking']['stage'], 'destination')
        resp = self.send_location(latitude=11.9, longitude=75.39)
        self.assertEqual(resp.data['tracking']['stage'], 'destination')
        self.assertGreater(resp.data['tracking']['distance_to_destination_km'], 0)
        self.assertIsNone(resp.data['tracking']['distance_to_pickup_km'])


class OTPTests(TrackingTestCase):
    def test_otp_issued_on_accept_shown_only_to_rider_and_hashed(self):
        self.accept()
        code = self.code()
        self.assertRegex(code, r'^\d{6}$')
        stored = RideOTP.objects.get(ride=self.ride)
        self.assertNotIn(code, json.dumps({'n': stored.nonce, 'h': stored.otp_hash}))

        self.as_user(self.rider)
        resp = self.client.get('/api/rider/ride/otp/')
        self.assertEqual(resp.data['otp'], code)
        # Driver-facing responses never contain the code.
        self.as_user(self.driver_user)
        for path in ('/api/driver/active-ride/', '/api/driver/rides/ongoing/'):
            self.assertNotIn(code, json.dumps(self.client.get(path).data, default=str))
        self.assertNotIn(code, json.dumps(self.send_location().data, default=str))
        self.as_user(self.driver_user)
        self.assertEqual(self.client.get('/api/rider/ride/otp/').status_code, 403)

    def test_valid_otp_starts_ride_and_cannot_be_reused(self):
        self.accept()
        code = self.code()
        self.client.post('/api/driver/ride/status/', {'ride_id': self.ride.id, 'status': 'ARRIVED'}, format='json')
        code = self.code()  # arriving issues a fresh code
        resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': code}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.ride.refresh_from_db()
        self.assertEqual((self.ride.status, self.ride.otp_verified), ('IN_PROGRESS', True))
        self.assertIsNotNone(self.ride.started_at)
        again = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': code}, format='json')
        self.assertEqual(again.status_code, 400)
        self.as_user(self.rider)
        self.assertEqual(self.client.get('/api/rider/ride/otp/').status_code, 404)  # hidden once used

    def test_wrong_codes_count_down_then_lock(self):
        self.accept()
        good = self.code()
        bad = '000000' if good != '000000' else '111111'
        for left in (4, 3, 2, 1):
            resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': bad}, format='json')
            self.assertEqual((resp.status_code, resp.data['attempts_left']), (400, left))
        resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': bad}, format='json')
        self.assertEqual(resp.data['code'], 'locked')
        # Even the right code is refused while locked.
        resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': good}, format='json')
        self.assertEqual(resp.data['code'], 'locked')
        self.assertEqual(OTPAttempt.objects.filter(ride=self.ride).count(), 6)
        self.assertEqual(OTPAttempt.objects.filter(ride=self.ride, success=True).count(), 0)

    def test_expired_code_rejected(self):
        self.accept()
        code = self.code()
        RideOTP.objects.filter(ride=self.ride).update(expires_at=timezone.now() - timedelta(seconds=1))
        resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': code}, format='json')
        self.assertEqual(resp.data['code'], 'expired')
        self.as_user(self.rider)
        self.assertTrue(self.client.get('/api/rider/ride/otp/').data['is_expired'])

    def test_regenerate_invalidates_old_code(self):
        self.accept()
        old = self.code()
        RideOTP.objects.filter(ride=self.ride).update(created_at=timezone.now() - timedelta(minutes=1))
        self.as_user(self.rider)
        new = self.client.post('/api/rider/ride/otp/regenerate/', {}, format='json').data['otp']
        self.assertNotEqual(old, new)
        self.as_user(self.driver_user)
        resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': old}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': new}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_regenerate_is_rate_limited(self):
        self.accept()
        self.as_user(self.rider)
        self.assertEqual(self.client.post('/api/rider/ride/otp/regenerate/', {}, format='json').status_code, 400)

    def test_unrelated_driver_cannot_verify_or_change_status(self):
        self.accept()
        code = self.code()
        self.as_user(self.other_driver_user)
        resp = self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': code}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], 'Ride not found.')
        resp = self.client.post('/api/driver/ride/status/', {'ride_id': self.ride.id, 'status': 'ARRIVED'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, 'ACCEPTED')


class StatusWorkflowTests(TrackingTestCase):
    def status(self, value):
        return self.client.post('/api/driver/ride/status/', {'ride_id': self.ride.id, 'status': value}, format='json')

    def test_only_valid_transitions(self):
        self.accept()
        self.assertEqual(self.status('IN_PROGRESS').status_code, 400)   # needs OTP
        self.assertEqual(self.status('COMPLETED').status_code, 400)     # not started
        self.assertEqual(self.status('ARRIVED').data['ride']['status'], 'ARRIVED')
        self.assertEqual(self.status('ARRIVED').status_code, 400)       # already arrived
        self.client.post('/api/driver/ride/verify-otp/', {'ride_id': self.ride.id, 'otp': self.code()}, format='json')
        self.assertEqual(self.status('COMPLETED').data['ride']['status'], 'COMPLETED')
        self.ride.refresh_from_db()
        self.assertIsNotNone(self.ride.completed_at)
        self.assertEqual(self.status('COMPLETED').status_code, 400)

    def test_driver_active_ride_endpoint(self):
        self.as_user(self.driver_user)
        self.assertIsNone(self.client.get('/api/driver/active-ride/').data['ride'])
        self.accept()
        self.send_location()
        data = self.client.get('/api/driver/active-ride/').data
        self.assertEqual(data['ride']['id'], self.ride.id)
        self.assertEqual(data['driver_status']['label'], 'On the way to pickup')
        self.assertEqual(data['rider']['full_name'], self.rider.full_name)


class TrackingPagesTests(TrackingTestCase):
    """The website pages (session login) for the same features."""

    def test_rider_track_page_only_for_owner(self):
        from django.urls import reverse
        self.client.force_authenticate(None)
        self.client.login(email='rider@example.com', password=PASSWORD)
        resp = self.client.get(reverse('riderpages:track_ride', args=[self.ride.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="trk-config"')
        self.client.login(email='other.rider@example.com', password=PASSWORD)
        self.assertEqual(self.client.get(reverse('riderpages:track_ride', args=[self.ride.id])).status_code, 404)

    def test_payment_redirects_to_tracking(self):
        from django.urls import reverse
        Ride.objects.filter(pk=self.ride.pk).update(status='PENDING', payment_method=None)
        self.client.login(email='rider@example.com', password=PASSWORD)
        resp = self.client.post(reverse('riderpages:booking_confirmation', args=[self.ride.id]), {'payment_method': 'cash'})
        self.assertRedirects(resp, reverse('riderpages:track_ride', args=[self.ride.id]))

    def test_driver_live_page_and_accept_redirect(self):
        from django.urls import reverse
        self.client.login(email='driver@example.com', password=PASSWORD)
        self.assertEqual(self.client.get(reverse('driverpages:live')).status_code, 200)
        resp = self.client.post(reverse('driverpages:accept_ride', args=[self.ride.id]))
        self.assertRedirects(resp, reverse('driverpages:live'))
        page = self.client.get(reverse('driverpages:live'))
        self.assertContains(page, f'"ride_id": {self.ride.id}')
        self.assertNotIn(self.code(), page.content.decode())  # OTP never sent to the driver page

    def test_session_api_calls_need_csrf(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        c.login(email='driver@example.com', password=PASSWORD)
        resp = c.post('/api/driver/location/update/', NEAR_PICKUP, content_type='application/json')
        self.assertEqual(resp.status_code, 403)  # no CSRF token
