from django.conf import settings
from django.db import models


class UserSession(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notely_session",
    )
    session_key = models.CharField(max_length=40, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReplacedSession(models.Model):
    session_key = models.CharField(max_length=40, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["created_at"])]
