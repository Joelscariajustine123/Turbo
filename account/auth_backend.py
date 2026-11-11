from django.contrib.auth.backends import ModelBackend

from .models import CustomUser


class EmailBackend(ModelBackend):
    """Authenticate with email + password.

    Also accepts ``username=`` because Django's admin site (and
    ``authenticate()`` callers in general) pass the USERNAME_FIELD value
    under that keyword.
    """

    def authenticate(self, request, email=None, password=None, username=None, **kwargs):
        email = email or username or kwargs.get(CustomUser.USERNAME_FIELD)
        if not email or password is None:
            return None
        try:
            user = CustomUser.objects.get(email__iexact=email.strip())
        except CustomUser.DoesNotExist:
            # Run the hasher anyway so response time doesn't reveal whether the email exists.
            CustomUser().set_password(password)
            return None
        except CustomUser.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
