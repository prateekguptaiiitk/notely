from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path("healthz/", lambda request: HttpResponse("ok", content_type="text/plain")),
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("notes.urls")),
    path(
        "robots.txt",
        lambda request: HttpResponse(
            "User-agent: *\nDisallow: /\n",
            content_type="text/plain",
        ),
    ),
]

handler403 = "config.views.error403"
handler404 = "config.views.error404"
handler500 = "config.views.error500"
