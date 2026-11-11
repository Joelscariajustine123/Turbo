from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from account.tests import PASSWORD, make_user

from .models import ContactMessage, Ride
from .pricing import calculate_fare, get_route

COORDS = {'pickup_lat': '11.8745', 'pickup_lng': '75.3704', 'drop_lat': '11.9500', 'drop_lng': '75.4200'}


class RiderPagesTests(TestCase):
    def setUp(self):
        self.rider = make_user('rider')
        self.client.login(email='rider@example.com', password=PASSWORD)

    def test_public_pages_render(self):
        for name in ('index', 'safety', 'outstation', 'services', 'contact'):
            self.assertEqual(self.client.get(reverse(f'riderpages:{name}')).status_code, 200, name)
        self.assertEqual(self.client.get(reverse('riderpages:map_view')).status_code, 200)

    def test_contact_form_saves(self):
        resp = self.client.post(reverse('riderpages:contact'),
                                {'name': 'A', 'email': 'a@example.com', 'message': 'Hi'})
        self.assertRedirects(resp, reverse('riderpages:contact'))
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_distance_and_fare_are_computed_on_server(self):
        resp = self.client.post(reverse('riderpages:map_view'), {
            'pickup': 'A', 'drop': 'B', 'car': 'sedan', 'distance': '1', 'fare': '1', **COORDS,
        })
        ride = Ride.objects.get()
        self.assertRedirects(resp, reverse('riderpages:track_ride', args=[ride.id]))
        self.assertEqual(ride.status, 'CONFIRMED')  # sent to drivers; paid after the ride
        route = get_route(11.8745, 75.3704, 11.95, 75.42)
        self.assertEqual(ride.distance, route.distance_km)  # posted distance of 1 is ignored
        self.assertEqual(ride.fare, calculate_fare('sedan', route.distance_km))
        self.assertGreater(ride.fare, Decimal('100'))

    def test_booking_without_coordinates_does_not_crash(self):
        resp = self.client.post(reverse('riderpages:map_view'),
                                {'pickup': 'A', 'drop': 'B', 'car': 'sedan', 'distance': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Ride.objects.exists())

    def test_confirm_with_upi_and_cash(self):
        ride = Ride.objects.create(user=self.rider, pickup_location='A', drop_location='B',
                                   car_type='bike', distance=5, fare=90)
        url = reverse('riderpages:booking_confirmation', args=[ride.id])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {'payment_method': 'upi', 'transaction_id': ''})
        ride.refresh_from_db()
        self.assertEqual(ride.status, 'PENDING')  # UPI needs a transaction id
        self.client.post(url, {'payment_method': 'upi', 'transaction_id': 'TX1'})
        ride.refresh_from_db()
        self.assertEqual((ride.status, ride.payment_method, ride.transaction_id), ('CONFIRMED', 'UPI', 'TX1'))

    def test_my_rides_and_cancel(self):
        ride = Ride.objects.create(user=self.rider, pickup_location='A', drop_location='B',
                                   car_type='bike', fare=90, status='CONFIRMED')
        self.assertContains(self.client.get(reverse('riderpages:my_rides')), 'Cancel')
        self.client.post(reverse('riderpages:cancel_ride', args=[ride.id]))
        ride.refresh_from_db()
        self.assertEqual(ride.status, 'CANCELLED')

    def test_cannot_view_other_riders_booking(self):
        other = make_user('rider', email='other@example.com')
        ride = Ride.objects.create(user=other, pickup_location='A', drop_location='B', car_type='bike')
        resp = self.client.get(reverse('riderpages:booking_confirmation', args=[ride.id]))
        self.assertEqual(resp.status_code, 404)


class PricingTests(TestCase):
    def test_osrm_failure_falls_back_and_backs_off(self):
        from unittest import mock

        from django.core.cache import cache
        from django.test import override_settings

        from . import pricing

        cache.clear()
        with override_settings(ROUTING_URL='http://osrm.invalid'), \
                mock.patch('urllib.request.urlopen', side_effect=OSError('down')) as urlopen:
            first = pricing.get_route(11.8745, 75.3704, 11.95, 75.42)
            second = pricing.get_route(11.8745, 75.3704, 11.95, 75.42)
        self.assertEqual((first.source, second.source), ('estimate', 'estimate'))
        self.assertEqual(urlopen.call_count, 1)  # second call skipped OSRM entirely
        cache.clear()

    def test_osrm_success_uses_road_distance(self):
        import io
        import json
        from unittest import mock

        from django.core.cache import cache
        from django.test import override_settings

        from . import pricing

        cache.clear()
        body = json.dumps({'routes': [{'distance': 12345.0,
                                       'geometry': {'coordinates': [[75.37, 11.87], [75.42, 11.95]]}}]})
        fake = mock.MagicMock()
        fake.__enter__.return_value = io.StringIO(body)
        with override_settings(ROUTING_URL='http://osrm.test'), mock.patch('urllib.request.urlopen', return_value=fake):
            route = pricing.get_route(11.8745, 75.3704, 11.95, 75.42)
        self.assertEqual((route.source, str(route.distance_km)), ('osrm', '12.35'))
        self.assertEqual(route.geometry[0], [11.87, 75.37])


class TrustPagesTests(TestCase):
    def test_privacy_terms_and_branded_login_pages(self):
        for name in ('privacy', 'terms'):
            self.assertEqual(self.client.get(reverse(f'riderpages:{name}')).status_code, 200)
        for name in ('rider_login', 'driver_login', 'admin_login', 'rider_signup', 'driver_signup'):
            page = self.client.get(reverse(f'account:{name}'))
            self.assertContains(page, 'Turbo Cab')
            self.assertContains(page, reverse('riderpages:privacy'))
            self.assertNotContains(page, 'saberali')
            self.assertNotContains(page, 'Logo_2013_Google')

    def test_search_console_verification_tag(self):
        from django.test import override_settings
        self.assertNotContains(self.client.get('/'), 'google-site-verification')
        with override_settings(GOOGLE_SITE_VERIFICATION='abc123token'):
            self.assertContains(self.client.get('/'), '<meta name="google-site-verification" content="abc123token" />',
                                html=False)


class SearchConsoleFileTests(TestCase):
    def test_verification_file_is_served_exactly(self):
        resp = self.client.get('/google696da265b08989c0.html')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode(), 'google-site-verification: google696da265b08989c0.html')
        self.assertEqual(self.client.get('/google0000000000000000.html').status_code, 404)
