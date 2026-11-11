import os

from django.core.management.base import BaseCommand

from account.models import CustomUser


class Command(BaseCommand):
    """Create the first Turbo admin from environment variables, if there is none yet.

    Runs on every deploy (see the Dockerfile) and does nothing once an admin exists:
        TURBO_ADMIN_EMAIL, TURBO_ADMIN_PASSWORD, TURBO_ADMIN_NAME (optional)
    The account can also log in to Django's /admin/ site.
    """

    help = 'Create the first admin account from TURBO_ADMIN_* environment variables.'

    def handle(self, *args, **options):
        email = os.environ.get('TURBO_ADMIN_EMAIL', '').strip().lower()
        password = os.environ.get('TURBO_ADMIN_PASSWORD', '')
        if not email or not password:
            self.stdout.write('ensure_admin: TURBO_ADMIN_EMAIL/PASSWORD not set, skipping.')
            return
        if CustomUser.objects.filter(role='admin').exists():
            self.stdout.write('ensure_admin: an admin already exists, nothing to do.')
            return
        if CustomUser.objects.filter(email__iexact=email).exists():
            self.stderr.write(f'ensure_admin: {email} is already used by a non-admin account.')
            return

        username = email.split('@')[0]
        while CustomUser.objects.filter(username__iexact=username).exists():
            username += '_'
        CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=os.environ.get('TURBO_ADMIN_NAME', 'Turbo Admin'),
            role='admin',
            is_staff=True,
            is_superuser=True,
        )
        self.stdout.write(self.style.SUCCESS(f'ensure_admin: created admin {email}.'))
