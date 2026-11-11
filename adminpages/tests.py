from django.test import TestCase
from django.urls import reverse

from account.models import CustomUser
from account.tests import PASSWORD, make_user
from riderpages.models import Ride


class AdminPagesTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin')
        self.rider = make_user('rider')
        Ride.objects.create(user=self.rider, pickup_location='A', drop_location='B',
                            car_type='bike', fare=90, status='COMPLETED')
        self.client.login(email='admin@example.com', password=PASSWORD)

    def test_all_pages_render(self):
        for name in ('home', 'dashboard', 'booking', 'payment', 'report', 'rider', 'settings'):
            self.assertEqual(self.client.get(reverse(f'adminpages:{name}')).status_code, 200, name)
        url = reverse('adminpages:edit_rider', args=[self.rider.id])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_home_stats(self):
        ctx = self.client.get(reverse('adminpages:home')).context
        self.assertEqual((ctx['total_riders'], ctx['total_bookings'], ctx['monthly_revenue']), (1, 1, 90))

    def test_booking_list_has_no_n_plus_one(self):
        for _ in range(5):
            Ride.objects.create(user=self.rider, pickup_location='A', drop_location='B', car_type='bike')
        # session + user + rides(with join) = 3, regardless of ride count
        with self.assertNumQueries(3):
            self.client.get(reverse('adminpages:booking'))

    def test_settings_shows_real_values_and_keeps_session_after_password_change(self):
        resp = self.client.get(reverse('adminpages:settings'))
        self.assertContains(resp, 'admin@example.com')
        resp = self.client.post(reverse('adminpages:settings'),
                                {'name': 'Boss', 'email': 'admin@example.com', 'password': 'An0ther-pass-456'})
        self.assertRedirects(resp, reverse('adminpages:settings'))
        self.assertEqual(self.client.get(reverse('adminpages:home')).status_code, 200)

    def test_delete_rider(self):
        resp = self.client.post(reverse('adminpages:delete_rider', args=[self.rider.id]))
        self.assertRedirects(resp, reverse('adminpages:rider'))
        self.assertFalse(CustomUser.objects.filter(role='rider').exists())
