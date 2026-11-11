from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.urls import reverse

LOGIN_URLS = {
    'rider': 'account:rider_login',
    'driver': 'account:driver_login',
    'admin': 'account:admin_login',
}


def role_required(role):
    """Allow access only to authenticated users with the given role.

    Anyone else is sent to that role's login page, with ?next= set so they
    land back on the page they asked for after logging in.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_authenticated and getattr(user, 'role', None) == role:
                return view_func(request, *args, **kwargs)
            return redirect_to_login(request.get_full_path(), reverse(LOGIN_URLS[role]))
        return _wrapped
    return decorator
