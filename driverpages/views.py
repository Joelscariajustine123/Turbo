from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from account.decorators import role_required

from . import services
from .models import AvailabilityStatus

driver_required = role_required('driver')


@driver_required
def homepage(request):
    driver = services.get_driver(request.user)
    return render(request, 'driverpages/homepage.html', {
        'driver': driver,
        'ride_requests': services.available_rides(driver),
        'ongoing_rides': services.ongoing_rides(driver),
    })


def _ride_action(request, ride_id, action, success_message, level=messages.SUCCESS):
    driver = services.get_driver(request.user)
    try:
        action(driver, ride_id)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.add_message(request, level, success_message)
    return redirect('driverpages:homepage')


@driver_required
@require_POST
def accept_ride(request, ride_id):
    return _ride_action(request, ride_id, services.accept_ride,
                        "Ride accepted! It is now listed under 'Ongoing Rides'.")


@driver_required
@require_POST
def complete_ride(request, ride_id):
    return _ride_action(request, ride_id, services.complete_ride, "Ride marked as complete!")


@driver_required
@require_POST
def decline_ride(request, ride_id):
    return _ride_action(request, ride_id, services.decline_ride,
                        "Ride declined. It won't be shown to you again.", messages.INFO)


@driver_required
def earnings(request):
    driver = services.get_driver(request.user)
    summary = services.earnings_summary(driver)
    context = {
        'driver': driver,
        **summary,
        'chart_labels': [row['date'].strftime('%d %b') for row in summary['chart']],
        'chart_data': [float(row['total']) for row in summary['chart']],
    }
    return render(request, 'driverpages/earning.html', context)


@driver_required
def profile(request):
    # The profile and settings pages edit the same data; keep one implementation.
    return redirect('driverpages:edit_profile')


@driver_required
def edit_profile(request):
    driver = services.get_driver(request.user)

    if request.method == 'POST':
        fields = ('full_name', 'phone', 'email', 'license_number', 'vehicle_info', 'availability_status')
        try:
            services.update_profile(
                driver,
                {k: request.POST.get(k, '') for k in fields},
                photo=request.FILES.get('profile_photo'),
            )
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
        else:
            messages.success(request, "Your settings have been saved.")
            return redirect('driverpages:edit_profile')

    return render(request, 'driverpages/settings.html', {
        'driver': driver,
        'availability_choices': AvailabilityStatus.choices,
    })
