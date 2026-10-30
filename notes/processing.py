import io
import tempfile
import uuid
from pathlib import Path

import fitz
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.db import transaction

from .models import NotePage
from .private_storage import delete_private, read_private, save_private


class InvalidNoteFile(Exception):
    """An upload does not contain a supported, valid image or PDF."""


def read_upload(upload):
    content = upload.read()
    upload.seek(0)
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise InvalidNoteFile(f"Maximum upload size is {settings.MAX_UPLOAD_MB} MB.")
    return content


def validate_content(filename, content):
    suffix = Path(filename).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png"}:
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise InvalidNoteFile("The uploaded image content is invalid.") from exc
        return "image", 1

    if suffix == ".pdf":
        try:
            document = fitz.open(stream=content, filetype="pdf")
            if not document.is_pdf or document.needs_pass:
                raise InvalidNoteFile("Password-protected or invalid PDFs are not supported.")
            count = document.page_count
        except InvalidNoteFile:
            raise
        except Exception as exc:
            raise InvalidNoteFile("The uploaded PDF content is invalid.") from exc
        if count < 1:
            raise InvalidNoteFile("The PDF has no pages.")
        if count > settings.MAX_PDF_PAGES:
            raise InvalidNoteFile(f"PDFs may have at most {settings.MAX_PDF_PAGES} pages.")
        return "pdf", count

    raise InvalidNoteFile("Only PNG, JPG, JPEG, and PDF files are accepted.")


def _render_image(content, output_dir, batch_id):
    with Image.open(io.BytesIO(content)) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail((settings.MAX_IMAGE_DIMENSION, settings.MAX_IMAGE_DIMENSION))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        output = output_dir / f"{batch_id}-1.webp"
        image.save(output, "WEBP", quality=80, method=5)
        return [(1, output, image.width, image.height)]


def _render_pdf(content, output_dir, batch_id):
    document = fitz.open(stream=content, filetype="pdf")
    rendered = []
    target_dpi_scale = 130 / 72
    for number, page in enumerate(document, start=1):
        rect = page.rect
        scale = min(
            target_dpi_scale,
            settings.MAX_IMAGE_DIMENSION / max(rect.width, rect.height) if max(rect.width, rect.height) else 1,
        )
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        output = output_dir / f"{batch_id}-{number}.webp"
        image.save(output, "WEBP", quality=80, method=5)
        rendered.append((number, output, image.width, image.height))
    return rendered


def process_upload(note, upload, retain_source=True):
    content = read_upload(upload)
    source_type, _ = validate_content(upload.name, content)
    batch_id = uuid.uuid4().hex
    old_source = note.source_path
    source_path = ""
    new_page_locations = []

    try:
        if retain_source:
            source_key = f"sources/{note.pk}/{uuid.uuid4().hex}{Path(upload.name).suffix.lower()}"
            source_path = save_private(source_key, content)
            note.source_path = source_path
            note.source_type = source_type
            note.processing_status = "pending"
            note.processing_error = ""
            note.save(
                update_fields=(
                    "source_path",
                    "source_type",
                    "processing_status",
                    "processing_error",
                    "updated_at",
                )
            )

        with tempfile.TemporaryDirectory(prefix="notely-pages-") as temporary_dir:
            output_dir = Path(temporary_dir)
            if source_type == "image":
                pages = _render_image(content, output_dir, batch_id)
            else:
                pages = _render_pdf(content, output_dir, batch_id)
            stored_pages = []
            for page_number, temp_path, width, height in pages:
                key = f"pages/{note.pk}/{batch_id}-{page_number}.webp"
                location = save_private(key, temp_path.read_bytes(), "image/webp")
                new_page_locations.append(location)
                stored_pages.append((page_number, location, width, height))

        old_page_paths = list(
            NotePage.objects.filter(note=note).values_list("image_path", flat=True)
        )

        try:
            with transaction.atomic():
                NotePage.objects.filter(note=note).delete()
                for page_number, location, width, height in stored_pages:
                    NotePage.objects.create(
                        note=note,
                        page_number=page_number,
                        image_path=location,
                        width=width,
                        height=height,
                    )
                note.source_type = source_type
                note.processing_status = "ready"
                note.processing_error = ""
                note.save()
        except Exception:
            _delete_quietly(new_page_locations)
            raise

        _delete_quietly(old_page_paths)
        if source_path and old_source and old_source != note.source_path:
            _delete_quietly([old_source])
    except Exception as exc:
        _delete_quietly(new_page_locations)
        note.processing_status = "failed"
        note.processing_error = str(exc)[:2000]
        note.save(update_fields=("processing_status", "processing_error", "updated_at"))
        raise


def _delete_quietly(locations):
    for location in locations:
        try:
            delete_private(location)
        except Exception:
            # File cleanup must not invalidate an otherwise successful upload.
            pass


def process_retained_source(note):
    if not note.source_path:
        raise InvalidNoteFile("No retained source file exists; upload the note again.")
    from django.core.files.uploadedfile import SimpleUploadedFile

    suffix = Path(note.source_path).suffix or ".pdf"
    upload = SimpleUploadedFile(f"note{suffix}", read_private(note.source_path))
    process_upload(note, upload, retain_source=True)
