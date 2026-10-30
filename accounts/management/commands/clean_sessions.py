from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import ReplacedSession, UserSession


class Command(BaseCommand):
    help = "Remove expired session replacement records and stale user session rows."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(seconds=settings.SESSION_COOKIE_AGE)
        replaced_count, _ = ReplacedSession.objects.filter(created_at__lt=cutoff).delete()
        stale_count = 0
        for row in UserSession.objects.all().iterator():
            active = Session.objects.filter(
                session_key=row.session_key,
                expire_date__gt=timezone.now(),
            ).exists()
            if not active:
                row.delete()
                stale_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {replaced_count} expired replacement records and "
                f"{stale_count} stale user sessions."
            )
        )
