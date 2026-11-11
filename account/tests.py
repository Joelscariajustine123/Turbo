from django.test import TestCase
from django.urls import reverse

from .models import CustomUser

PASSWORD = 'Str0ng-pass-123'


def make_user(role, email=None, **extra):
    email = email or f'{role}@example.com'
    return CustomUser.objects.create_user(
        username=email.split('@')[0], email=email, password=PASSWORD,
        full_name=f'{role.title()} User', role=role, **extra,
    )


class SignupTests(TestCase):
    def post_signup(self, url_name, **overrides):
        data = {
            'full_name': 'New Person', 'username': 'newperson', 'email': 'New@Example.com',
            'password1': PASSWORD, 'password2': PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse(url_name), data)

    def test_rider_signup_creates_rider_with_hashed_password(self):
        resp = self.post_signup('account:rider_signup')
        self.assertRedirects(resp, reverse('account:rider_login'))
        user = CustomUser.objects.get(email='new@example.com')
        self.assertEqual(user.role, 'rider')
        self.assertTrue(user.check_password(PASSWORD))

    def test_admin_signup_closes_after_first_admin(self):
        self.assertRedirects(self.post_signup('account:admin_signup'), reverse('account:admin_login'))
        resp = self.post_signup('account:admin_signup', username='second', email='second@example.com')
        self.assertRedirects(resp, reverse('account:admin_login'))
        self.assertEqual(CustomUser.objects.filter(role='admin').count(), 1)
        # ...but a logged-in admin can still add one
        self.client.login(email='new@example.com', password=PASSWORD)
        self.post_signup('account:admin_signup', username='second', email='second@example.com')
        self.assertEqual(CustomUser.objects.filter(role='admin').count(), 2)

    def test_admin_signup_mismatch_rerenders_with_error(self):
        resp = self.post_signup('account:admin_signup', password2='other')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Passwords do not match')
        self.assertFalse(CustomUser.objects.exists())

    def test_duplicate_username_does_not_crash(self):
        make_user('rider', email='newperson@example.com')
        resp = self.post_signup('account:driver_signup', email='other@example.com')
        self.assertContains(resp, 'Username is already taken')

    def test_weak_password_rejected(self):
        resp = self.post_signup('account:rider_signup', password1='123', password2='123')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CustomUser.objects.exists())


class LoginTests(TestCase):
    def test_login_by_role(self):
        make_user('driver')
        resp = self.client.post(reverse('account:driver_login'),
                                {'email': 'DRIVER@example.com', 'password': PASSWORD})
        self.assertRedirects(resp, reverse('driverpages:homepage'))

    def test_wrong_role_rejected(self):
        make_user('rider')
        resp = self.client.post(reverse('account:admin_login'),
                                {'email': 'rider@example.com', 'password': PASSWORD})
        self.assertContains(resp, 'Invalid email or password')

    def test_next_redirect_and_unsafe_next_ignored(self):
        make_user('rider')
        map_url = reverse('riderpages:map_view')
        resp = self.client.post(reverse('account:rider_login') + f'?next={map_url}',
                                {'email': 'rider@example.com', 'password': PASSWORD})
        self.assertRedirects(resp, map_url)
        self.client.logout()
        resp = self.client.post(reverse('account:rider_login'),
                                {'email': 'rider@example.com', 'password': PASSWORD,
                                 'next': 'https://evil.example.com/'})
        self.assertRedirects(resp, reverse('riderpages:index'))

    def test_logout(self):
        make_user('rider')
        self.client.login(email='rider@example.com', password=PASSWORD)
        self.client.get(reverse('account:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_django_admin_site_login_works_with_email_backend(self):
        make_user('admin', is_staff=True, is_superuser=True)
        resp = self.client.post(reverse('admin:login'),
                                {'username': 'admin@example.com', 'password': PASSWORD})
        self.assertEqual(resp.status_code, 302)


class RoleGuardTests(TestCase):
    def test_rider_cannot_open_admin_or_driver_pages(self):
        make_user('rider')
        self.client.login(email='rider@example.com', password=PASSWORD)
        resp = self.client.get(reverse('adminpages:home'))
        self.assertTrue(resp.url.startswith(reverse('account:admin_login')))
        resp = self.client.get(reverse('driverpages:homepage'))
        self.assertTrue(resp.url.startswith(reverse('account:driver_login')))

    def test_anonymous_redirected_to_matching_login(self):
        resp = self.client.get(reverse('riderpages:map_view'))
        self.assertTrue(resp.url.startswith(reverse('account:rider_login') + '?next='))
