from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.shortcuts import redirect
from django.utils import timezone

from .models import ReplacedSession, UserSession


class ActiveSingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        if not request.user.is_authenticated and cookie_key:
            replaced = ReplacedSession.objects.filter(session_key=cookie_key).first()
            if replaced:
                if timezone.now() - replaced.created_at <= timedelta(
                    seconds=settings.SESSION_COOKIE_AGE
                ):
                    replaced.delete()
                    messages.error(
                        request,
                        "You were signed out because your account was used on another device.",
                    )
                    return redirect("login")
                replaced.delete()

        user = request.user
        if user.is_authenticated:
            if not user.is_active:
                logout(request)
                messages.error(request, "Your account is inactive. Contact an administrator.")
                return redirect("login")

            current = UserSession.objects.filter(user=user).first()
            if current and current.session_key and current.session_key != request.session.session_key:
                # Keep the new device record; only clear this request's session.
                request.session.flush()
                messages.error(
                    request,
                    "You were signed out because your account was used on another device.",
                )
                return redirect("login")

            if current is None and request.session.session_key:
                exists = Session.objects.filter(
                    session_key=request.session.session_key,
                    expire_date__gt=timezone.now(),
                ).exists()
                if not exists:
                    logout(request)
                    return redirect("login")

        return self.get_response(request)
