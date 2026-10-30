from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.html import format_html

from .forms import NoteAdminForm
from .models import Note, NotePage, ViewLog
from .processing import process_upload
from .private_storage import delete_private, delete_private_prefix


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    form = NoteAdminForm
    list_display = (
        "preview_thumbnail",
        "title",
        "source_type",
        "processing_status",
        "is_published",
        "position",
        "created_at",
    )
    list_filter = ("source_type", "processing_status", "is_published")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    actions = ("publish_notes", "unpublish_notes")
    readonly_fields = (
        "processing_status",
        "processing_error",
        "created_at",
        "updated_at",
        "page_preview",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("pages")

    @admin.display(description="Preview")
    def preview_thumbnail(self, obj):
        page = next(iter(obj.pages.all()), None)
        if not page or obj.processing_status != "ready":
            return "—"
        url = reverse(
            "notes:admin_page_preview",
            args=(obj.pk, page.page_number),
        )
        return format_html(
            '<a href="{}"><img src="{}" alt="Note preview" loading="lazy" '
            'style="width:72px;height:auto"></a>',
            url,
            url,
        )

    @admin.display(description="Processed page preview")
    def page_preview(self, obj):
        if not obj or not obj.pk:
            return "Save and process the note to see a preview."
        page = obj.pages.first()
        if not page or obj.processing_status != "ready":
            return "No processed pages are available."
        url = reverse(
            "notes:admin_page_preview",
            args=(obj.pk, page.page_number),
        )
        return format_html(
            '<img src="{}" alt="Preview of page {}" loading="lazy" '
            'style="max-width:360px;height:auto">',
            url,
            page.page_number,
        )

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            raise PermissionDenied
        super().save_model(request, obj, form, change)
        upload = form.cleaned_data.get("upload")
        if upload:
            obj.processing_status = "pending"
            obj.processing_error = ""
            obj.save(update_fields=("processing_status", "processing_error"))
            try:
                process_upload(obj, upload)
            except Exception as exc:
                obj.processing_status = "failed"
                obj.processing_error = str(exc)[:2000]
                obj.save(update_fields=("processing_status", "processing_error"))
                messages.error(request, f"Note saved, but processing failed: {exc}")
            else:
                messages.success(request, "Note pages processed successfully.")

    @admin.action(description="Publish selected notes")
    def publish_notes(self, request, queryset):
        queryset.filter(processing_status="ready").update(is_published=True)

    @admin.action(description="Unpublish selected notes")
    def unpublish_notes(self, request, queryset):
        queryset.update(is_published=False)

    def delete_model(self, request, obj):
        note_id = obj.pk
        for page in obj.pages.all():
            try:
                delete_private(page.image_path)
            except Exception:
                pass
        if obj.source_path:
            try:
                delete_private(obj.source_path)
            except Exception:
                pass
        delete_private_prefix(f"pages/{note_id}")
        delete_private_prefix(f"sources/{note_id}")
        cache_root = settings.PRIVATE_STORAGE_DIR / "watermarked"
        if cache_root.exists():
            for user_cache in cache_root.iterdir():
                for cached_file in user_cache.glob(f"{note_id}-*.jpg"):
                    cached_file.unlink(missing_ok=True)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for note in queryset:
            self.delete_model(request, note)


@admin.register(ViewLog)
class ViewLogAdmin(admin.ModelAdmin):
    list_display = ("user", "note", "page", "timestamp", "ip")
    list_filter = ("timestamp", "note")
    search_fields = ("user__username", "note__title")
    readonly_fields = ("user", "note", "page", "timestamp", "ip")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotePage)
class NotePageAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
