import hashlib
import io
import time
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from .models import Note, NotePage, ViewLog
from .private_storage import read_private


CSP = (
    "default-src 'self'; img-src 'self'; connect-src 'self'; "
    "style-src 'self'; script-src 'self'; object-src 'none'; "
    "base-uri 'self'; frame-ancestors 'none'"
)


def private_headers(response):
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["X-Frame-Options"] = "DENY"
    response["Referrer-Policy"] = "no-referrer"
    response["Content-Security-Policy"] = CSP
    return response


def _same_origin_url(value, request):
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return False
    expected_scheme = "https" if request.is_secure() else "http"
    return parsed.scheme == expected_scheme and parsed.netloc.lower() == request.get_host().lower()


def _passes_fetch_checks(request):
    destination = request.headers.get("Sec-Fetch-Dest")
    if destination and destination not in {"image", "empty"}:
        return False
    if destination == "empty":
        mode = request.headers.get("Sec-Fetch-Mode")
        site = request.headers.get("Sec-Fetch-Site")
        if mode and mode not in {"cors", "same-origin"}:
            return False
        if site and site not in {"same-origin", "none"}:
            return False
    origin = request.headers.get("Origin")
    if origin == "null" and settings.RUNNING_DEV_SERVER:
        origin = None
    if origin and not _same_origin_url(origin, request):
        return False
    referer = request.headers.get("Referer")
    if referer and not _same_origin_url(referer, request):
        return False
    return True


@login_required
@never_cache
def note_list(request):
    notes = Note.objects.filter(
        is_published=True,
        processing_status="ready",
    ).only("title", "slug", "created_at", "description")
    response = render(request, "notes/list.html", {"notes": notes})
    return private_headers(response)


@login_required
@never_cache
def note_detail(request, slug):
    note = get_object_or_404(
        Note.objects.filter(is_published=True, processing_status="ready"),
        slug=slug,
    )
    pages = list(note.pages.only("page_number", "width", "height").all())
    ViewLog.objects.create(
        user=request.user,
        note=note,
        page=0,
        ip=request.META.get("REMOTE_ADDR"),
    )
    response = render(
        request,
        "notes/viewer.html",
        {"note": note, "pages": pages},
    )
    return private_headers(response)


def _watermark(image):
    text = "copyright @Notely"
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    tile = Image.new("RGBA", (480, 140), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((12, 48), text, font=font, fill=(25, 25, 25, 32))
    tile = tile.rotate(25, expand=True)
    for y in range(-(tile.height // 2), image.height, tile.height):
        for x in range(-(tile.width // 2), image.width, tile.width):
            overlay.alpha_composite(tile, (x, y))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _private_page_response(request, note, note_page):
    cache_dir = settings.PRIVATE_STORAGE_DIR / "watermarked" / str(request.user.pk)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Version the cache key so changed watermark pixels replace older renders.
    cache_path = cache_dir / f"{note.pk}-{note_page.pk}-wm3.jpg"
    if cache_path.is_file() and time.time() - cache_path.stat().st_mtime < 3600:
        data = cache_path.read_bytes()
    else:
        try:
            original = read_private(note_page.image_path)
        except (OSError, ValueError):
            raise Http404 from None
        with Image.open(io.BytesIO(original)) as source:
            image = source.convert("RGB")
        image = _watermark(image)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82, optimize=True)
        data = buffer.getvalue()
        cache_path.write_bytes(data)

    response = HttpResponse(data, content_type="image/jpeg")
    response["Content-Disposition"] = "inline"
    return private_headers(response)


@login_required
@never_cache
def page_image(request, slug, page):
    if not _passes_fetch_checks(request):
        raise Http404
    note = get_object_or_404(
        Note.objects.filter(is_published=True, processing_status="ready"),
        slug=slug,
    )
    note_page = get_object_or_404(NotePage, note=note, page_number=page)
    return _private_page_response(request, note, note_page)


@login_required
@never_cache
def admin_page_preview(request, note_id, page):
    if not request.user.is_superuser:
        raise Http404
    note = get_object_or_404(Note, pk=note_id, processing_status="ready")
    note_page = get_object_or_404(NotePage, note=note, page_number=page)
    return _private_page_response(request, note, note_page)
