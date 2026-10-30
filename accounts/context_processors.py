from django.utils import timezone


def viewer_context(request):
    user = request.user
    return {
        "viewer_name": user.username if user.is_authenticated else "",
        "viewer_id": user.pk if user.is_authenticated else "",
        "viewer_time": timezone.localtime(),
    }
