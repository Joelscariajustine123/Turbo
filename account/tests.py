from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CustomUser

PASSWORD = 'Str0ng-pass-123'


def make_user(role, email=None, **extra):
    """An existing, email-verified account (like every account created before email codes)."""
    email = email or f'{role}@example.com'
    extra.setdefault('email_verified', True)
    return CustomUser.objects.create_user(
        username=email.split('@')[0], email=email, password=PASSWORD,
        full_name=f'{role.title()} User', role=role, **extra,
    )


def code_from_mail():
    """The 6-digit code from the latest email (subject: "123456 is your Turbo verification code")."""
    return mail.outbox[-1].subject.split()[0]


class SignupTests(TestCase):
    def post_signup(self, url_name, **overrides):
        data = {
            'full_name': 'New Person', 'username': 'newperson', 'email': 'New@Example.com',
            'password1': PASSWORD, 'password2': PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse(url_name), data)

    def test_rider_signup_requires_email_code(self):
        resp = self.post_signup('account:rider_signup')
        self.assertRedirects(resp, reverse('account:verify_email'))
        user = CustomUser.objects.get(email='new@example.com')
        self.assertEqual(user.role, 'rider')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.email_verified)
        self.assertEqual(mail.outbox[-1].to, ['new@example.com'])
        resp = self.client.post(reverse('account:verify_email'), {'code': code_from_mail()})
        self.assertRedirects(resp, reverse('riderpages:index'))
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertIn('_auth_user_id', self.client.session)

    def test_admin_signup_closes_after_first_admin(self):
        self.assertRedirects(self.post_signup('account:admin_signup'), reverse('account:verify_email'))
        self.client.post(reverse('account:verify_email'), {'code': code_from_mail()})
        self.client.logout()
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
    def test_login_by_role_needs_emailed_code(self):
        make_user('driver')
        resp = self.client.post(reverse('account:driver_login'),
                                {'email': 'DRIVER@example.com', 'password': PASSWORD})
        self.assertRedirects(resp, reverse('account:verify_email'))
        self.assertNotIn('_auth_user_id', self.client.session)  # not logged in yet
        self.assertIn('log in', mail.outbox[-1].body)
        resp = self.client.post(reverse('account:verify_email'), {'code': code_from_mail()})
        self.assertRedirects(resp, reverse('driverpages:homepage'))

    def test_wrong_code_counts_down_and_code_is_single_use(self):
        make_user('rider')
        self.client.post(reverse('account:rider_login'), {'email': 'rider@example.com', 'password': PASSWORD})
        good = code_from_mail()
        bad = '000000' if good != '000000' else '111111'
        resp = self.client.post(reverse('account:verify_email'), {'code': bad}, follow=True)
        self.assertContains(resp, '4 attempts left')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.client.post(reverse('account:verify_email'), {'code': good})
        self.assertIn('_auth_user_id', self.client.session)
        self.client.logout()
        # reusing the same code doesn't work
        self.client.post(reverse('account:rider_login'), {'email': 'rider@example.com', 'password': PASSWORD})
        from account.models import EmailOTP
        EmailOTP.objects.update(created_at=EmailOTP.objects.first().created_at)
        resp = self.client.post(reverse('account:verify_email'), {'code': good}, follow=True)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_resend_is_rate_limited(self):
        make_user('rider')
        self.client.post(reverse('account:rider_login'), {'email': 'rider@example.com', 'password': PASSWORD})
        resp = self.client.post(reverse('account:verify_email'), {'action': 'resend'}, follow=True)
        self.assertContains(resp, 'Please wait')
        self.assertEqual(len(mail.outbox), 1)

    def test_unverified_account_gets_registration_code_at_login(self):
        make_user('rider', email_verified=False)
        self.client.post(reverse('account:rider_login'), {'email': 'rider@example.com', 'password': PASSWORD})
        self.assertIn('finish creating your Turbo account', mail.outbox[-1].body)
        self.client.post(reverse('account:verify_email'), {'code': code_from_mail()})
        self.assertTrue(CustomUser.objects.get(email='rider@example.com').email_verified)

    def test_email_failure_shows_error_instead_of_crashing(self):
        make_user('rider')
        with mock.patch('account.email_otp.send_mail', side_effect=OSError('SMTP blocked')):
            resp = self.client.post(reverse('account:rider_login'), {'email': 'rider@example.com', 'password': PASSWORD})
        self.assertContains(resp, 'send the verification email right now')
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(EMAIL_OTP_ENABLED=False)
    def test_codes_can_be_switched_off(self):
        make_user('driver')
        resp = self.client.post(reverse('account:driver_login'), {'email': 'driver@example.com', 'password': PASSWORD})
        self.assertRedirects(resp, reverse('driverpages:homepage'))

    def test_wrong_role_rejected(self):
        make_user('rider')
        resp = self.client.post(reverse('account:admin_login'),
                                {'email': 'rider@example.com', 'password': PASSWORD})
        self.assertContains(resp, 'Invalid email or password')

    def test_next_redirect_and_unsafe_next_ignored(self):
        make_user('rider')
        map_url = reverse('riderpages:map_view')
        self.client.post(reverse('account:rider_login') + f'?next={map_url}',
                         {'email': 'rider@example.com', 'password': PASSWORD})
        resp = self.client.post(reverse('account:verify_email'), {'code': code_from_mail()})
        self.assertRedirects(resp, map_url)
        self.client.logout()
        from account.models import EmailOTP
        EmailOTP.objects.all().delete()  # skip the resend cooldown
        self.client.post(reverse('account:rider_login'),
                         {'email': 'rider@example.com', 'password': PASSWORD, 'next': 'https://evil.example.com/'})
        resp = self.client.post(reverse('account:verify_email'), {'code': code_from_mail()})
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


class EnsureAdminCommandTests(TestCase):
    def run_cmd(self, **env):
        import os
        from io import StringIO
        from unittest import mock

        from django.core.management import call_command

        out = StringIO()
        with mock.patch.dict(os.environ, env, clear=False):
            call_command('ensure_admin', stdout=out, stderr=out)
        return out.getvalue()

    def test_creates_admin_and_ignores_stray_whitespace(self):
        out = self.run_cmd(TURBO_ADMIN_EMAIL=' Admin@Turbo.com\n', TURBO_ADMIN_PASSWORD='admin@123\n')
        self.assertIn('created admin admin@turbo.com', out)
        self.assertTrue(CustomUser.objects.get(email='admin@turbo.com').email_verified)
        self.client.post(reverse('account:admin_login'), {'email': 'admin@turbo.com', 'password': 'admin@123'})
        resp = self.client.post(reverse('account:verify_email'), {'code': code_from_mail()})
        self.assertRedirects(resp, reverse('adminpages:home'))

    def test_does_nothing_twice_and_reset_changes_password(self):
        self.run_cmd(TURBO_ADMIN_EMAIL='admin@turbo.com', TURBO_ADMIN_PASSWORD='first-pass-1')
        self.assertIn('already exists', self.run_cmd(TURBO_ADMIN_EMAIL='admin@turbo.com', TURBO_ADMIN_PASSWORD='other'))
        self.assertTrue(CustomUser.objects.get().check_password('first-pass-1'))
        self.run_cmd(TURBO_ADMIN_EMAIL='admin@turbo.com', TURBO_ADMIN_PASSWORD='second-pass-2', TURBO_ADMIN_RESET='true')
        self.assertTrue(CustomUser.objects.get().check_password('second-pass-2'))


# ---------------------------------------------------------------- Sign in with Google

CLIENT_ID = 'test-client.apps.googleusercontent.com'


def _rsa_key():
    from cryptography.hazmat.primitives.asymmetric import rsa
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@override_settings(GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID)
class GoogleTokenVerificationTests(TestCase):
    """The real verifier, with a locally generated signing key standing in for Google's."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.key = _rsa_key()
        cls.other_key = _rsa_key()

    def token(self, key=None, **overrides):
        import time

        import jwt
        now = int(time.time())
        claims = {'iss': 'https://accounts.google.com', 'aud': CLIENT_ID, 'sub': '1234567890',
                  'email': 'Asha@Gmail.com', 'email_verified': True, 'name': 'Asha K', 'iat': now, 'exp': now + 600}
        claims.update(overrides)
        return jwt.encode(claims, key or self.key, algorithm='RS256', headers={'kid': 'k1'})

    def verify(self, token):
        from account import google_auth
        signing = mock.Mock(key=self.key.public_key())
        with mock.patch.object(google_auth, '_keys') as keys:
            keys.return_value.get_signing_key_from_jwt.return_value = signing
            return google_auth.verify_id_token(token)

    def assertRejected(self, token, code):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError) as ctx:
            self.verify(token)
        self.assertEqual(ctx.exception.code, code)

    def test_valid_token(self):
        claims = self.verify(self.token())
        self.assertEqual((claims['sub'], claims['email']), ('1234567890', 'Asha@Gmail.com'))

    def test_rejects_wrong_audience_issuer_expiry_signature_and_unverified_email(self):
        import time
        self.assertRejected(self.token(aud='another-app'), 'invalid')
        self.assertRejected(self.token(iss='https://evil.example.com'), 'issuer')
        self.assertRejected(self.token(exp=int(time.time()) - 3600, iat=int(time.time()) - 7200), 'expired')
        self.assertRejected(self.token(key=self.other_key), 'invalid')  # not signed by "Google"
        self.assertRejected(self.token(email_verified=False), 'unverified')
        self.assertRejected('not-a-jwt', 'invalid')

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='')
    def test_disabled_without_client_id(self):
        self.assertRejected(self.token(), 'disabled')


@override_settings(GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID)
class GoogleSignInTests(TestCase):
    """Account creation / linking rules (token verification mocked)."""

    def claims(self, **extra):
        return {'sub': 'g-111', 'email': 'asha@gmail.com', 'email_verified': True, 'name': 'Asha K', **extra}

    def post(self, role, claims=None):
        import json
        with mock.patch('account.google_auth.verify_id_token', return_value=claims or self.claims()):
            return self.client.post(reverse('account:google_login'), json.dumps({'credential': 'x', 'role': role}),
                                    content_type='application/json')

    def test_new_rider_is_created_verified_and_logged_in_without_email_code(self):
        resp = self.post('rider')
        self.assertEqual(resp.json()['redirect'], reverse('riderpages:index'))
        user = CustomUser.objects.get(email='asha@gmail.com')
        self.assertEqual((user.role, user.google_sub, user.email_verified, user.full_name),
                         ('rider', 'g-111', True, 'Asha K'))
        self.assertFalse(user.has_usable_password())
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(len(mail.outbox), 0)  # Google already verified the email

    def test_new_driver_goes_to_profile_setup(self):
        self.assertEqual(self.post('driver').json()['redirect'], reverse('driverpages:edit_profile'))

    def test_existing_password_account_is_linked(self):
        make_user('rider', email='asha@gmail.com', email_verified=False)
        self.post('rider')
        user = CustomUser.objects.get(email='asha@gmail.com')
        self.assertEqual((user.google_sub, user.email_verified), ('g-111', True))
        self.assertTrue(user.check_password(PASSWORD))  # password still works too
        self.assertEqual(CustomUser.objects.count(), 1)

    def test_wrong_role_is_refused(self):
        make_user('driver', email='asha@gmail.com')
        resp = self.post('rider')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('registered as a driver', resp.json()['detail'])
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_admins_are_never_created_by_google(self):
        resp = self.post('admin')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(CustomUser.objects.exists())
        make_user('admin', email='asha@gmail.com')
        self.assertEqual(self.post('admin').json()['redirect'], reverse('adminpages:home'))

    def test_email_linked_to_another_google_account_is_refused(self):
        make_user('rider', email='asha@gmail.com', google_sub='g-999')
        self.assertIn('different Google account', self.post('rider').json()['detail'])

    def test_inactive_account_is_refused(self):
        make_user('rider', email='asha@gmail.com', is_active=False)
        self.assertEqual(self.post('rider').status_code, 400)

    def test_needs_csrf_token(self):
        import json

        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        with mock.patch('account.google_auth.verify_id_token', return_value=self.claims()):
            resp = c.post(reverse('account:google_login'), json.dumps({'credential': 'x', 'role': 'rider'}),
                          content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    def test_no_google_button_on_any_auth_page(self):
        # Google sign-in was removed from the pages: no Google script, logo or button text anywhere.
        for name in ('rider_login', 'driver_login', 'admin_login', 'rider_signup', 'driver_signup', 'usertype'):
            body = self.client.get(reverse(f'account:{name}')).content.decode()
            self.assertNotIn('accounts.google.com', body, name)
            self.assertNotIn('with Google', body, name)
            self.assertNotIn('Logo_2013_Google', body, name)

    def test_api_google_login_returns_tokens(self):
        from rest_framework.test import APIClient
        with mock.patch('account.google_auth.verify_id_token', return_value=self.claims()):
            resp = APIClient().post('/api/auth/google/', {'credential': 'x', 'role': 'rider'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['created'])
        self.assertIn('access', resp.data)
        self.assertEqual(APIClient().get('/api/meta/').data['google_client_id'], CLIENT_ID)
