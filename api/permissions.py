from rest_framework.permissions import BasePermission


class _HasRole(BasePermission):
    role = None
    message = "You don't have access to this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, 'role', None) == self.role)


class IsRider(_HasRole):
    role = 'rider'
    message = "Only riders can do this."


class IsDriver(_HasRole):
    role = 'driver'
    message = "Only drivers can do this."


class IsAdminRole(_HasRole):
    role = 'admin'
    message = "Only admins can do this."
