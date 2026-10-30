from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.sessions.models import Session
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from .forms import AccessLoginForm
from .models import ReplacedSession, UserSession
from .rate_limit import clear_failures, is_blocked, record_failure


@never_cache
@csrf_protect
def login_view(request):
    form = AccessLoginForm(request.POST or None)
    ip_address = request.META.get("REMOTE_ADDR", "")

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        access_code = form.cleaned_data["access_code"]
        if is_blocked(ip_address, username):
            messages.error(request, "Invalid credentials")
            return render(request, "accounts/login.html", {"form": form}, status=429)

        user = authenticate(request, username=username, password=access_code)
        if user is None or not user.is_active:
            record_failure(ip_address, username)
            messages.error(request, "Invalid credentials")
            return render(request, "accounts/login.html", {"form": form})

        previous = UserSession.objects.filter(user=user).first()
        if previous and previous.session_key:
            active = Session.objects.filter(
                session_key=previous.session_key,
                expire_date__gt=timezone.now(),
            ).exists()
            if not active:
                previous.delete()
            elif settings.SINGLE_SESSION_POLICY == "block":
                messages.error(request, "Invalid credentials")
                return render(request, "accounts/login.html", {"form": form})
            else:
                ReplacedSession.objects.update_or_create(
                    session_key=previous.session_key,
                    defaults={"user": user},
                )
                Session.objects.filter(session_key=previous.session_key).delete()

        clear_failures(ip_address, username)
        login(request, user)
        UserSession.objects.update_or_create(
            user=user,
            defaults={"session_key": request.session.session_key},
        )
        return redirect("notes:list")

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have signed out.")
    return redirect("login")
