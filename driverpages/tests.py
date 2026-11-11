from django.test import TestCase
from django.urls import reverse

from account.tests import PASSWORD, make_user
from riderpages.models import Ride

from .models import DriverProfile, Earning


class DriverFlowTests(TestCase):
    def setUp(self):
        self.rider = make_user('rider')
        self.driver_user = make_user('driver', phone='9876543210')
        self.driver = DriverProfile.objects.get(user=self.driver_user)  # created by signal
        self.client.login(email='driver@example.com', password=PASSWORD)
        self.ride = Ride.objects.create(user=self.rider, pickup_location='A', drop_location='B',
                                        car_type='sedan', distance=10, fare=200, status='CONFIRMED')

    def test_pages_render(self):
        for name in ('homepage', 'earnings', 'edit_profile'):
            self.assertEqual(self.client.get(reverse(f'driverpages:{name}')).status_code, 200, name)
        self.assertRedirects(self.client.get(reverse('driverpages:profile')),
                             reverse('driverpages:edit_profile'))

    def test_accept_then_complete_records_earning(self):
        self.client.post(reverse('driverpages:accept_ride', args=[self.ride.id]))
        self.ride.refresh_from_db()
        self.assertEqual((self.ride.status, self.ride.driver), ('ACCEPTED', self.driver))
        self.assertFalse(Earning.objects.exists())

        # Completing before the passenger's OTP is verified is refused.
        self.client.post(reverse('driverpages:complete_ride', args=[self.ride.id]))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, 'ACCEPTED')

        # (This ride has no map coordinates, so the 50 m rule doesn't apply.)
        from driverpages import services
        from riderpages import otp
        services.mark_arrived(self.driver, self.ride.id)
        services.verify_pickup_otp(self.driver, self.ride.id, otp.for_rider(self.ride).code)
        self.client.post(reverse('driverpages:complete_ride', args=[self.ride.id]))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, 'COMPLETED')
        self.assertEqual(Earning.objects.get().amount, 200)

        resp = self.client.get(reverse('driverpages:earnings'))
        self.assertContains(resp, 'earningsChart')
        self.assertEqual(resp.context['chart_data'], [200.0])

    def test_decline_hides_ride_only_for_that_driver(self):
        self.client.post(reverse('driverpages:decline_ride', args=[self.ride.id]))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, 'CONFIRMED')  # still open for other drivers
        self.assertNotContains(self.client.get(reverse('driverpages:homepage')), 'Accept</button>')
        make_user('driver', email='driver2@example.com')
        self.client.login(email='driver2@example.com', password=PASSWORD)
        self.assertContains(self.client.get(reverse('driverpages:homepage')), 'Accept</button>')

    def test_ride_actions_require_post(self):
        resp = self.client.get(reverse('driverpages:accept_ride', args=[self.ride.id]))
        self.assertEqual(resp.status_code, 405)

    def test_second_driver_cannot_take_accepted_ride(self):
        self.client.post(reverse('driverpages:accept_ride', args=[self.ride.id]))
        make_user('driver', email='driver2@example.com')
        self.client.login(email='driver2@example.com', password=PASSWORD)
        self.client.post(reverse('driverpages:accept_ride', args=[self.ride.id]))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.driver, self.driver)

    def test_edit_profile_saves(self):
        resp = self.client.post(reverse('driverpages:edit_profile'), {
            'full_name': 'D Two', 'phone': '1234567890', 'email': 'driver@example.com',
            'license_number': 'KL13', 'vehicle_info': 'Swift', 'availability_status': 'offline',
        })
        self.assertRedirects(resp, reverse('driverpages:edit_profile'))
        self.driver.refresh_from_db()
        self.assertEqual((self.driver.license_number, self.driver.availability_status), ('KL13', 'offline'))

    def test_edit_profile_rejects_taken_email(self):
        resp = self.client.post(reverse('driverpages:edit_profile'), {
            'full_name': 'D', 'phone': '1234567890', 'email': 'rider@example.com',
            'license_number': 'KL13', 'vehicle_info': 'Swift', 'availability_status': 'offline',
        })
        self.assertContains(resp, 'already exists')
