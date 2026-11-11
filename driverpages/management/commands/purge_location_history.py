from django.core.management.base import BaseCommand

from driverpages.tracking import purge_history


class Command(BaseCommand):
    help = 'Delete trip GPS breadcrumbs older than TURBO_TRACK_RETENTION_DAYS (default 30).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=None, help='Override the retention period.')

    def handle(self, *args, days=None, **options):
        deleted = purge_history(days)
        self.stdout.write(f'purge_location_history: deleted {deleted} old location points.')
