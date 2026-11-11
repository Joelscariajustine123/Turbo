import os

from django.core.management.base import BaseCommand

from account.models import CustomUser


class Command(BaseCommand):
    """Create the first Turbo admin from environment variables, if there is none yet.

    Runs on every deploy (see the Dockerfile):
        TURBO_ADMIN_EMAIL, TURBO_ADMIN_PASSWORD, TURBO_ADMIN_NAME (optional)
    Set TURBO_ADMIN_RESET=true to (re)set the password of TURBO_ADMIN_EMAIL on the
    next deploy — e.g. if you forgot it — then remove the variable again.
    The account can also log in to Django's /admin/ site.
    """

    help = 'Create the first admin account from TURBO_ADMIN_* environment variables.'

    def handle(self, *args, **options):
        # Values pasted into a dashboard often pick up a stray space or newline.
        email = os.environ.get('TURBO_ADMIN_EMAIL', '').strip().lower()
        password = os.environ.get('TURBO_ADMIN_PASSWORD', '').strip()
        reset = os.environ.get('TURBO_ADMIN_RESET', '').strip().lower() in ('1', 'true', 'yes')

        if not email or not password:
            self.stdout.write('ensure_admin: TURBO_ADMIN_EMAIL/PASSWORD not set, skipping.')
            return

        existing = CustomUser.objects.filter(email__iexact=email).first()
        if existing is not None:
            if existing.role != 'admin':
                self.stderr.write(f'ensure_admin: {email} belongs to a {existing.role} account, not an admin.')
            elif reset:
                existing.set_password(password)
                existing.is_active = True
                existing.save(update_fields=['password', 'is_active'])
                self.stdout.write(self.style.SUCCESS(
                    f'ensure_admin: password reset for {email}. Remove TURBO_ADMIN_RESET now.'))
            else:
                self.stdout.write(f'ensure_admin: admin {email} already exists, nothing to do.')
            return

        if CustomUser.objects.filter(role='admin').exists():
            admins = ', '.join(CustomUser.objects.filter(role='admin').values_list('email', flat=True))
            self.stdout.write(f'ensure_admin: admin account(s) already exist ({admins}); not creating {email}.')
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
