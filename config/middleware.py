from django.conf import settings


class LocalAdminOriginMiddleware:
    """Normalize an opaque local admin-login origin before Django CSRF checks.

    Some embedded local browser contexts send Origin: null even for a form
    opened from this server. Restrict the normalization to runserver and the
    admin login endpoint. Django's standard CsrfViewMiddleware still checks
    the CSRF cookie and submitted form token after this middleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        admin_prefix = f"/{settings.ADMIN_URL.strip('/')}/"
        if (
            settings.RUNNING_DEV_SERVER
            and request.method == "POST"
            and request.headers.get("Origin") == "null"
            and request.path.startswith(admin_prefix)
        ):
            scheme = "https" if request.is_secure() else "http"
            request.META["HTTP_ORIGIN"] = f"{scheme}://{request.get_host()}"
        return self.get_response(request)
