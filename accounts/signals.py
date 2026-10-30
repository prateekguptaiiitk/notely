from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver

from .models import UserSession


@receiver(user_logged_out)
def clear_user_session(sender, request, user, **kwargs):
    if user is not None:
        UserSession.objects.filter(user=user).delete()
