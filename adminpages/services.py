"""Admin dashboard queries shared by the website views and the REST API."""
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from account.models import CustomUser
from riderpages.models import TRIP_STATUSES, ContactMessage, Ride


def dashboard_stats():
    now = timezone.now()
    stats = Ride.objects.aggregate(
        total_rides=Count('id'),
        total_bookings=Count('id', filter=Q(status='COMPLETED')),
        pending_requests=Count('id', filter=Q(status='PENDING')),
        waiting_for_driver=Count('id', filter=Q(status='CONFIRMED')),
        ongoing_rides=Count('id', filter=Q(status__in=TRIP_STATUSES)),
        monthly_revenue=Sum('fare', filter=Q(
            status='COMPLETED', created_at__year=now.year, created_at__month=now.month)),
        total_revenue=Sum('fare', filter=Q(status='COMPLETED')),
    )
    users = CustomUser.objects.aggregate(
        total_riders=Count('id', filter=Q(role='rider')),
        total_drivers=Count('id', filter=Q(role='driver')),
    )
    stats['monthly_revenue'] = stats['monthly_revenue'] or 0
    stats['total_revenue'] = stats['total_revenue'] or 0
    stats['unread_messages'] = ContactMessage.objects.count()
    return {**stats, **users}


def daily_reports():
    return (
        Ride.objects.order_by()  # clear Meta.ordering so GROUP BY is only the date
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(
            total_rides=Count('id'),
            completed_rides=Count('id', filter=Q(status='COMPLETED')),
            cancelled_rides=Count('id', filter=Q(status='CANCELLED')),
            total_revenue=Sum('fare', filter=Q(status='COMPLETED')),
        )
        .order_by('-date')
    )
